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

# Load LAME encoder DLL
lameDllPath = os.path.join(os.path.dirname(__file__), "libs", "libmp3lame.dll")
lame = ctypes.CDLL(lameDllPath)

# LAME function prototypes
lame.lame_init.argtypes = []
lame.lame_init.restype = ctypes.c_void_p

lame.lame_set_in_samplerate.argtypes = [ctypes.c_void_p, ctypes.c_int]
lame.lame_set_in_samplerate.restype = ctypes.c_int

lame.lame_set_num_channels.argtypes = [ctypes.c_void_p, ctypes.c_int]
lame.lame_set_num_channels.restype = ctypes.c_int

lame.lame_set_brate.argtypes = [ctypes.c_void_p, ctypes.c_int]
lame.lame_set_brate.restype = ctypes.c_int

lame.lame_init_params.argtypes = [ctypes.c_void_p]
lame.lame_init_params.restype = ctypes.c_int

lame.lame_encode_buffer.argtypes = [
	ctypes.c_void_p,					 # lame_global_flags* (context pointer)
	ctypes.POINTER(ctypes.c_short),	  # Left channel PCM input buffer
	ctypes.POINTER(ctypes.c_short),	  # Right channel PCM input buffer (or None for mono)
	ctypes.c_int,						# Number of samples per channel
	ctypes.POINTER(ctypes.c_ubyte),	  # MP3 output buffer
	ctypes.c_int						 # MP3 buffer size
]
lame.lame_encode_buffer.restype = ctypes.c_int


lame.lame_close.argtypes = [ctypes.c_void_p]
lame.lame_close.restype = ctypes.c_int


def initLame(channels, sampleRate, bitrate=128):
	"""Initialize LAME encoder with standard API."""
	lameContext = lame.lame_init()
	if not lameContext:
		raise RuntimeError("Failed to initialize LAME encoder.")

	# Set parameters
	if lame.lame_set_in_samplerate(lameContext, sampleRate) != 0:
		raise RuntimeError("Failed to set input sample rate.")
	if lame.lame_set_num_channels(lameContext, channels) != 0:
		raise RuntimeError("Failed to set number of channels.")
	if lame.lame_set_brate(lameContext, bitrate) != 0:
		raise RuntimeError("Failed to set bitrate.")

	# Finalize parameters
	if lame.lame_init_params(lameContext) != 0:
		raise RuntimeError("Failed to initialize encoder parameters.")

	return lameContext

lameContext = None
def encodeAudioToMp3(inputData, sampleRate=44100, channels=1, bitrate=128, initial=False):
	"""Encode raw PCM audio data to MP3."""
	global lameContext
	log.info(f'zzz Encode audio to mp3')
	if initial:
		lameContext = initLame(channels, sampleRate, bitrate)

	# Test:
	# import math
	# d = [int(32000*math.sin(2*math.pi*220/44100*i)) for i in range(1,int(44100*4.8))]
	# d = b''.join(s.to_bytes(2, byteorder="little", signed=True) for s in d)
	# inputData = bytearray(d)

	# Check if input data length matches the expected sample width
	if len(inputData) % 2 != 0:
		raise ValueError("Input data length must be a multiple of 2 for 16-bit audio.")

	# Prepare input and output buffers
	numSamples = len(inputData) // 2  # 2 bytes per sample for 16-bit audio
	log.info(f'zzz {numSamples=}')
	inputBuffer = (ctypes.c_short * numSamples).from_buffer(bytearray(inputData))
	mp3BufferSize = int(1.25 * len(inputData) + 7200)  # Recommended buffer size
	log.info(f'zzz {mp3BufferSize=}')
	mp3Buffer = (ctypes.c_ubyte * mp3BufferSize)()

	# Encode audio
	bytesWritten = lame.lame_encode_buffer(
		lameContext,
		inputBuffer,   # Mono PCM data
		None,		  # No right channel
		numSamples,	# Total samples in the buffer
		mp3Buffer,
		mp3BufferSize,
	)
	log.info(f"{bytesWritten=}")
	del inputBuffer

	# Check if bytesWritten exceeds the allocated buffer size
	if bytesWritten > mp3BufferSize:
		raise RuntimeError(
			f"LAME encoder wrote {bytesWritten} bytes, which exceeds the buffer size of {mp3BufferSize}."
		)
	elif bytesWritten < 0:
		lame.lame_close(lameContext)
		lameContext = None
		
		raise RuntimeError(f"LAME encoding error: {bytesWritten}")

	# Convert to bytes and clean up
	mp3Data = bytes(mp3Buffer[:bytesWritten])
	del mp3Buffer
	return mp3Data


class AudioRecord:
	def __init__(self, filePath):
		self.filePath = filePath
		self.recordsPath = os.path.dirname(self.filePath)
		self.isRecording = False
		self.recordingComplete = False
		self.audio = pyaudio.PyAudio()
		self.stream = None
		self.audioBuffer = bytearray()
		self.lock = threading.Lock()
		self.interval = 10  # Save interval in seconds
		self.initial = None

	def _recordAudio(self):
		global lameContext
		self.stream = self.audio.open(
			format=pyaudio.paInt16,
			channels=1,
			rate=44100,
			input=True,
			frames_per_buffer=1024,
		)
		startTime = time.time()
		self.initial = True
		while self.isRecording:
			data = self.stream.read(1024)
			with self.lock:
				self.audioBuffer.extend(data)
			if time.time() - startTime >= self.interval:
				with self.lock:
					self.saveRecording()
				startTime = time.time()
		lame.lame_close(lameContext)
		lameContext = None

	def startRecording(self):
		if self.isRecording:
			raise RuntimeError("Already recording.")
		self.isRecording = True
		threading.Thread(target=self._recordAudio).start()

	def stopRecording(self):
		self.isRecording = False
		if self.stream:
			self.stream.stop_stream()
			self.stream.close()
			self.saveRecording()
			self.recordingComplete = True
			return True
		return False

	def saveRecording(self):
		if not self.audioBuffer:
			return
		mp3Data = encodeAudioToMp3(self.audioBuffer, initial=self.initial)
		self.initial = False
		self.audioBuffer.clear()
		with open(self.filePath, "ab") as mp3File:
			mp3File.write(mp3Data)

	def play(self):
		alias = "mp3player"
		mci = ctypes.windll.winmm

		def _send_command(command):
			"""Send an MCI command."""
			result = mci.mciSendStringW(command, None, 0, None)
			if result != 0:
				raise RuntimeError(f"MCI error: {result}")

		log.info("zzz start playing")
		command = f'open "{self.filePath}" type mpegvideo alias {alias}'
		_send_command(command)
		_send_command(f'play {alias}')
		import time
		time.sleep(5)
		_send_command(f'stop {alias}')
		_send_command(f'close {alias}')
		log.info("zzz end playing")

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
		fileName = f"{timestamp}_audio.mp3"
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
		if self.record and self.record.isRecording:
			try:
				saved = self.record.stopRecording()
			except Exception:
				log.exception("Error while saving current recording")
			else:
				if not saved:
					log.error("Error whil saving recording")
		super().terminate()
