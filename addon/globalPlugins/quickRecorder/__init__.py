# -*- coding: UTF-8 -*-
# NVDA add-on: Quick Rrecorder.
# Copyright (C) 2025 Cyrille Bougot
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

import os
import sys
import wave
import threading
from datetime import datetime

import globalPluginHandler
import addonHandler
from scriptHandler import script
import ui
from logHandler import log


ADDON_SUMMARY = addonHandler.getCodeAddon().manifest["summary"]

addonHandler.initTranslation()


def getPyaudio():
	"""Import pyaudio compatible with current Python version."""
	MAJORPYTHONVER = sys.version_info.major
	MINORPYTHONVER = sys.version_info.minor
	pyaudioPath = os.path.join(
		os.path.dirname(__file__),
		"libs",
		"py{0}{1}".format(MAJORPYTHONVER, MINORPYTHONVER)
	)
	try:
		sys.path.append(pyaudioPath)
		from logHandler import log
		log.debug(sys.path[-1])
		import pyaudio
		del sys.path[-1]
		return pyaudio
	except Exception:
		#raise ImportError(f"No pyaudio found for Python version {MAJORPYTHONVER}.{MINORPYTHONVER}", exc_info=True)
		log.debugWarning(f"No pyaudio found for Python version {MAJORPYTHONVER}.{MINORPYTHONVER}", exc_info=True)
		raise


pyaudio = getPyaudio()



class AudioRecord:
	def __init__(self, filePath):
		self.filePath = filePath
		self.recordsPath = os.path.dirname(self.filePath)
		self.isRecording = False
		self.recordingComplete = False
		self.audio = pyaudio.PyAudio()
		self.stream = None
		self.frames = []
		self.recordingThread = None

	def _record_audio(self):
		"""Private method to record audio in a separate thread."""
		self.frames = []
		self.stream = self.audio.open(format=pyaudio.paInt16,
									  channels=1,
									  rate=44100,
									  input=True,
									  frames_per_buffer=1024)

		while self.isRecording:
			data = self.stream.read(1024)
			self.frames.append(data)

	def startRecording(self):
		"""Start recording audio asynchronously in a separate thread."""
		if self.isRecording:
			raise RuntimeError("Already recording.")

		self.isRecording = True
		log.debug("Recording started.")
		
		# Create and start a new thread for recording
		self.recordingThread = threading.Thread(target=self._record_audio)
		self.recordingThread.start()

	def stopRecording(self):
		"""Stop recording audio.
		Returns True if the audio has been saved and False otherwise.
		"""

		if not self.isRecording:
			raise RuntimeError("Not currently recording.")

		self.isRecording = False
		if self.recordingThread:
			self.recordingThread.join()
		self.stream.stop_stream()
		self.stream.close()
		self.recordingComplete = True
		log.debug("Recording stopped.")
		return self.saveRecording()

	def saveRecording(self):
		"""Save the recorded audio to a file.
		Returns True if audio has been saved and false if no audio could be saved.
		"""
		if not self.frames:
			return False
		if not os.path.isdir(self.recordsPath):
			os.makedirs(self.recordsPath)
		with wave.open(self.filePath, 'wb') as wf:
			wf.setnchannels(1)
			wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
			wf.setframerate(44100)
			wf.writeframes(b''.join(self.frames))
		log.debug(f"Audio saved as {self.filePath}")
		return True

	def play(self):
		"""Play the recorded audio."""
		if not os.path.exists(self.filePath):
			raise FileNotFoundError(f"Audio file does not exist {self.filePath}")

		log.debug("Playing audio...")
		wf = wave.open(self.filePath, 'rb')
		stream = self.audio.open(
			format=self.audio.get_format_from_width(wf.getsampwidth()),
			channels=wf.getnchannels(),
			rate=wf.getframerate(),
			output=True,
		)

		data = wf.readframes(1024)
		while data:
			stream.write(data)
			data = wf.readframes(1024)
		stream.stop_stream()
		stream.close()
		log.debug("Audio playback finished.")


import time
import ctypes
zzzz

# Load LAME encoder DLL
lameDllPath = os.path.join(os.path.dirname(__file__), "libs", "lame_enc.dll")
lame = ctypes.CDLL(lameDllPath)

# LAME function prototypes
lame.encodeInit = lame.lame_init
lame.encodeInit.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
lame.encodeInit.restype = ctypes.c_void_p

lame.encodeBufferInterleaved = lame.lame_encode_buffer_interleaved
lame.encodeBufferInterleaved.argtypes = [
	ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ubyte)
]
lame.encodeBufferInterleaved.restype = ctypes.c_int

# Initialize LAME encoder (Mono, 44100Hz, 128 kbps bitrate)
def initLame(channels, sampleRate, bitrate=128):
	return lame.encodeInit(channels, sampleRate, bitrate, 0)

# Encoding function
def encodeAudioToMp3(inputData):
	lameContext = initLame(1, 44100, 128)  # Mono, 44100Hz, 128 kbps

	# Allocate space for the MP3 data
	outputData = ctypes.create_string_buffer(len(inputData) * 2)

	# Encode audio
	bytesWritten = lame.encodeBufferInterleaved(
		lameContext, len(inputData), inputData, outputData
	)

	# Return the MP3 data
	return outputData.raw[:bytesWritten]

class AudioRecord:
	def __init__(self, filePath):
		self.filePath = filePath
		self.recordsPath = os.path.dirname(self.filePath)
		self.isRecording = False
		self.recordingComplete = False
		self.audio = pyaudio.PyAudio()
		self.stream = None
		self.frames = []
		self.recordingThread = None
		self.audioBuffer = bytearray()  # To store raw audio data for encoding
		self.lock = threading.Lock()  # To ensure thread safety
		self.interval = 10  # Time interval for writing to disk in seconds

	def _recordAudio(self):
		"""Private method to record audio in a separate thread."""
		self.frames = []
		self.stream = self.audio.open(format=pyaudio.paInt16,
									  channels=1,
									  rate=44100,
									  input=True,
									  frames_per_buffer=1024)

		while self.isRecording:
			data = self.stream.read(1024)
			with self.lock:
				self.audioBuffer.extend(data)  # Add audio data to buffer

	def startRecording(self):
		"""Start recording audio asynchronously in a separate thread."""
		if self.isRecording:
			raise RuntimeError("Already recording.")

		self.isRecording = True
		log.debug("Recording started.")
		
		# Create and start a new thread for recording
		self.recordingThread = threading.Thread(target=self._recordAudio)
		self.recordingThread.start()

	def stopRecording(self):
		"""Stop recording audio and save to MP3.
		Returns True if the audio has been saved and False otherwise.
		"""

		if not self.isRecording:
			raise RuntimeError("Not currently recording.")

		self.isRecording = False
		if self.recordingThread:
			self.recordingThread.join()
		self.stream.stop_stream()
		self.stream.close()
		self.recordingComplete = True
		log.debug("Recording stopped.")
		return self.saveRecording()

	def saveRecording(self):
		"""Save the recorded audio to an MP3 file, written at regular intervals."""
		if not self.audioBuffer:
			return False

		if not os.path.isdir(self.recordsPath):
			os.makedirs(self.recordsPath)

		# Periodically save the audio buffer to MP3
		with open(self.filePath, 'wb') as mp3File:
			startTime = time.time()
			while self.audioBuffer:
				# Every interval seconds, encode and write to MP3
				if time.time() - startTime >= self.interval:
					mp3Data = encodeAudioToMp3(self.audioBuffer)
					mp3File.write(mp3Data)
					self.audioBuffer.clear()  # Clear the buffer after writing
					startTime = time.time()  # Reset the timer

				time.sleep(0.1)  # Simulate periodic recording, adjust as needed

		log.debug(f"Audio saved as {self.filePath}")
		return True

	def play(self):
		"""Play the recorded MP3 audio."""
		if not os.path.exists(self.filePath):
			raise FileNotFoundError(f"Audio file does not exist {self.filePath}")

		log.debug("Playing audio...")
		with open(self.filePath, 'rb') as mp3File:
			# You could use any MP3 playback library here (e.g., pydub, playsound, etc.)
			# For simplicity, we'll assume you're handling the playback with an external player
			pass

		log.debug("Audio playback finished.")

class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.record = None
		documentsPath = os.path.join(os.path.expanduser("~"), "Documents")
		self.recordsPath = os.path.join(documentsPath, "QuickRecorder")

	@script(
		description=_(
			# Translators: The message presented in input help mode.
			"Start recording an audio record",
		),
		category=ADDON_SUMMARY,
	)
	def script_startRecording(self, gesture):
		if self.record and self.record.isRecording:
			ui.message("Already recording zzz")
			return
		filePath = self.generateRecordFilePath()
		self.record = AudioRecord(filePath)
		ui.message("Recording zzz")
		self.record.startRecording()

	@script(
		description=_(
			# Translators: The message presented in input help mode.
			"Stops recording",
		),
		category=ADDON_SUMMARY,
	)
	def script_stopRecording(self, gesture):
		if not self.record:
			ui.message("No recording in progress zzz")
			return
		saved = self.record.stopRecording()
		if saved:
			ui.message("Recording stopped zzz")
		else:
			ui.message("Recording stopped; no record saved. zzz")

	def generateRecordFilePath(self):
		timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
		fileName = f"{timestamp}_audio.wav"
		filePath = os.path.join(self.recordsPath, fileName)
		counter = 1
		while os.path.exists(filePath):
			fileName = f"{timestamp}_audio_{counter}.wav"
			filePath = os.path.join(self.recordsPath, fileName)
			counter += 1
		return filePath

	@script(
		description=_(
			"Play the last recorded audio file",
		),
		category=ADDON_SUMMARY,
	)
	def script_playLastRecord(self, gesture):
		if not self.record:
			ui.message("No last record zzz")
			return
		if not self.record.recordingComplete:
			ui.message("Recording not yet available zzz")
			return
		if not os.path.exists(self.record.filePath):
			ui.message("Record file not found zzz")
			return

		def playAudio():
			"""Thread target for playing the audio file."""
			try:
				log.debug(f"Playing {self.record.filePath} zzz")
				self.record.play()
			except Exception as e:
				log.error(f"Error while playing the last record: {e}")
		
		playbackThread = threading.Thread(target=playAudio, daemon=True)
		playbackThread.start()

	def terminate(self):
		super().terminate()
