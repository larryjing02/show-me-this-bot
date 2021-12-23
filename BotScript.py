import json
import random
from serpapi import GoogleSearch
import discord
from discord.ext.commands import Bot

import speech_recognition as sr
import spacy

import config

bot = Bot(command_prefix='$')

# Global Bot Variables
bot.show = False

# Global Script Variables
filename = "data.json"
with open(filename, "r") as file:
	data = json.load(file)

r = sr.Recognizer()
nlp = spacy.load('en_core_web_sm')
verbose = True
readout = True
dur = 7
# Set default image for edge case
prev = "hawaii"
api_safe = False

@bot.event
async def on_ready():
	print(f'Bot connected as {bot.user}')

@bot.event
async def on_message(message):
	if not message.author == bot.user:
		msg = message.content.lower()
		if msg.startswith("test"):
			await message.channel.send('Hey there!')

		if msg.startswith('show') and not bot.show:
			await message.channel.send('Let\'s see what we have here...')
			await bot.change_presence(activity=discord.Game(name="the words"))
			bot.show = True
		elif msg.startswith('listen'):
			await message.channel.send('Let\'s take a listen here...')
			await bot.change_presence(activity=discord.Game(name="the sounds"))
			await listen(message)
			await message.channel.send('Time to stop listening.')

			await bot.change_presence()

		elif msg.startswith('quit') and (bot.show or bot.listen):
			await message.channel.send('Time to stop playing around.')
			await bot.change_presence()
			bot.show = False
			bot.listen = False
		elif msg.startswith('goodbye'):
			await message.channel.send('Goodbye! Going to sleep now.')
			await bot.change_presence()
			quit()
		elif bot.show:
			print(f"Searching for: {msg}")
			url = processQuery(msg)
			await message.channel.send(url)
			

def getThumbnails(query):
	params = {
		"q": query,
		"tbm": "isch",
		"ijn": "0",
		"api_key": config.search_api
	}
	#return "key", ["val1","val2"]

	search = GoogleSearch(params)
	results = search.get_dict()
	images_results = results['images_results']
	print(f"\t{len(images_results)} images sourced and stored")
	return query, [r['thumbnail'] for r in images_results]


def writeJson(res):
	global filename, data
	with open(filename, "r+") as file:
		temp = json.load(file)
		temp[res[0]] = res[1]
		file.seek(0)
		json.dump(temp, file, indent = 4)
		data = temp

def processQuery(query):
	query = query.strip().lower()
	global data
	if not data:
		if verbose:
			print("Loading data for first time")
		with open(filename, "r") as file:
			data = json.load(file)
		global prev
		prev = random.choice([data.keys()])
	if query not in data:
		# Remove (backup safety key)
		if api_safe:
			print("Cancelling")
			return f"I don't know what \"{query}\" looks like"
		else:
			print("\tUnrecognized Query: calling API")
			writeJson(getThumbnails(query))
	return random.choice(data[query])



def getSpeech():
	text = ""
	with sr.Microphone() as source:
		# read the audio data from the default microphone
		if verbose:
			print("Recording now!")
		audio_data = r.record(source, duration=dur)
		if verbose:
			print("Recognizing...")
		# convert speech to text
		try:
			text = r.recognize_google(audio_data)
			#text = r.recognize_sphinx(audio_data)
		except:
			if verbose:
				print("Silence Detected")
		if readout:
			print(text)
	return text

def listenMic():
	text = ""
	with sr.Microphone() as source:
		# read the audio data from the default microphone
		if verbose:
			print("Recording now!")
		# r.adjust_for_ambient_noise(source)
		audio_data = r.listen(source)
		if verbose:
			print("Recognizing...")
		# convert speech to text
		try:
			text = r.recognize_google(audio_data)
			#text = r.recognize_sphinx(audio_data)
		except:
			if verbose:
				print("Silence Detected")
		if readout:
			print(text)
	return text

# Returns -1 if quit
# Returns empty string if nothing queried
# Returns word if single word
# Returns everything following "show me (a)"
# Returns list of targets
def isolateTarget(sent):
	sent = sent.lower().strip()
	words = sent.split()
	if "quit" in words:
		return -1
	if "repeat" in words:
		return -2
	if len(words) == 0:
		return ""
	elif len(words) == 1:
		return words[0]
	
	# Override with "Show me" command:
	for i in range(len(words) - 2):
		if words[i] == "show" and words[i+1] == "me":
			if words[i+2] == "a":
				return " ".join(words[i+3:])
			return " ".join(words[i+2:])
	
	# Use natural language processing lib
	doc = nlp(sent)
	
	# Process sentence for noun phrases
	NP_list = [p for p in doc.noun_chunks]

	# Isolate nouns from sentence
	nouns = [w for w in doc if w.pos_=='NOUN']

	# Seek determiners
	dets = set([w.text for w in doc if w.pos_=='DET'])
	
	# Seek pronouns
	pron = set([w.text for w in doc if w.pos_=='PRON'])
	
	# Print out details
	if verbose:
		print(f"Noun Phrases:\t{NP_list}")
		print(f"Nouns:       \t{nouns}")
		print(f"Determinants:\t{dets}")
		print(f"Pronouns:    \t{pron}")
	
	# Filter pronouns, remove determiners
	targets = []
	for np in NP_list:
		np = np.text
		if np not in pron:
			words = [w for w in np.split() if w not in dets]
			targets.append(" ".join(words))           
	
	return targets

async def listen(message):
	global prev
	while(True):
		res = None

		r.energy_threshold = 300

		# if verbose:
		#     print("Adjusting for ambient noise")
		# with sr.Microphone() as source:
		#     r.adjust_for_ambient_noise(source, duration = 1)
		#     if verbose:
		#         print("Audio calibration complete")

		target = isolateTarget(listenMic())
		# target = isolateTarget(getSpeech())
		if target == -1:
			print("Quitting...")
			break
		if target == -2:
			if verbose:
				print("Repeating previous query")
				res = prev
		elif len(target) == 0:
			continue
		# If list, return item from list
		elif type(target) == list:
			global data
			for t in target:
				if t in data:
					if verbose:
						print(f"{t} is recognized out of {target}")
					res = t
			if not res:
				if verbose:
					print("Selecting random target out of {target}")
				res = random.choice(target)
			print(f"TARGET: {res}")
		# If string, return item
		else:
			res = target
			print(f"TARGET: {res}")
		if res:
			prev = res
			url = processQuery(res)
			await message.channel.send(url)


# Token for PythonTestBot#9025
bot.run(config.python_test_bot)