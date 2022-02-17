#!/usr/bin/env python
"""test script to find microphone on a given machine,
make test recording
"""
# %%
import os
from pathlib import Path

import pandas as pd

pd.set_option('display.max_columns', 500)
pd.set_option('display.max_rows', 500)
pd.set_option('display.width', 1000)
pd.options.display.float_format = '{:,.2f}'.format
#%%
# specific libaries
# this step requires pyaudio which itself requires a complex installation of port audio
# see: https://stackoverflow.com/questions/36681836/pyaudio-could-not-import-portaudio
import pyaudio
p = pyaudio.PyAudio()
for ii in range(p.get_device_count()):
    print("index {0:d} name {1}".format(ii, p.get_device_info_by_index(ii).get('name')))
# from this, we get entries 'pulse' and 'default'
#%%

#
"""
index 0 name HDA Intel PCH: CX20753/4 Analog (hw:0,0)
index 1 name HDA Intel PCH: HDMI 0 (hw:0,3)
index 2 name HDA Intel PCH: HDMI 1 (hw:0,7)
index 3 name HDA Intel PCH: HDMI 2 (hw:0,8)
index 4 name HDA Intel PCH: HDMI 3 (hw:0,9)
index 5 name HDA Intel PCH: HDMI 4 (hw:0,10)
index 6 name NSRT_mk3_Dev: USB Audio (hw:1,0)
index 7 name sysdefault
index 8 name front
index 9 name surround40
index 10 name surround51
index 11 name surround71
index 12 name hdmi
index 13 name samplerate
index 14 name speexrate
index 15 name pulse
index 16 name upmix
index 17 name vdownmix
index 18 name dmix
index 19 name default

"""
#%%
# okay, propetries for device 6
from pprint import pprint
import pyaudio
p = pyaudio.PyAudio()
props = p.get_device_info_by_index(6)
pprint(props)
"""
{'defaultHighInputLatency': 0.032,
 'defaultHighOutputLatency': -1.0,
 'defaultLowInputLatency': 0.008,
 'defaultLowOutputLatency': -1.0,
 'defaultSampleRate': 48000.0,
 'hostApi': 0,
 'index': 6,
 'maxInputChannels': 1,
 'maxOutputChannels': 0,
 'name': 'NSRT_mk3_Dev: USB Audio (hw:1,0)',
 'structVersion': 2}
"""
#%%
import sounddevice as sd

samplerates = 32000, 44100, 48000, 96000, 128000
device = 6
channel = 1
supported_samplerates = []
for fs in samplerates:
    try:
        sd.check_output_settings(device=device, channels=channel, samplerate=fs)
    except Exception as e:
        print(fs, e)
    else:
        supported_samplerates.append(fs)
print(supported_samplerates)

#%%
# NOTE this works on E560 Laptop if you are logged in to the actual laptop only
#  for raspberry pi, install sudo apt-get install libportaudio0 libportaudio2 libportaudiocpp0 portaudio19-dev
#  See: https://makersportal.com/blog/2018/8/23/recording-audio-on-the-raspberry-pi-with-python-and-a-usb-microphone

#%%
import wave
import pyaudio
# back to 0 as pulse audio...
form_1 = pyaudio.paInt16 # 16-bit resolution
chans = 1 # 1 channel
samp_rate = 48000 # 44.1kHz sampling rate
chunk = 1000 # 2^12 samples for buffer
record_secs = 60 # seconds to record
dev_index = 6 # device index found by p.get_device_info_by_index(ii)
wav_output_filename = './logs/test1.wav' # name of .wav file
audio = pyaudio.PyAudio() # create pyaudio instantiation
#%%
# create pyaudio stream
stream = audio.open(format = form_1,rate = samp_rate,channels = chans,
                    input_device_index = dev_index,input = True,
                    frames_per_buffer=chunk)
# stream = audio.open(
#     format = pyaudio.paInt16,
#     channels = 2,
#     rate = 48000,
#     input_device_index = 1,
#     input = True)

print("recording")
frames = []

# loop through stream and append audio chunks to frame array
for ii in range(0,int((samp_rate/chunk)*record_secs)):
    data = stream.read(chunk, exception_on_overflow=False)
    frames.append(data)

print("finished recording")

# stop the stream, close it, and terminate the pyaudio instantiation
stream.stop_stream()
stream.close()
audio.terminate()
#%%
# save the audio frames as .wav file
if Path(wav_output_filename).exists():
    print("deleting {0}".format(wav_output_filename))
    os.remove(wav_output_filename)
wavefile = wave.open(wav_output_filename,'wb')
wavefile.setnchannels(chans)
wavefile.setsampwidth(audio.get_sample_size(form_1))
wavefile.setframerate(samp_rate)
wavefile.writeframes(b''.join(frames))
wavefile.close()
#%%
# play wavfile
import pyaudio
import wave

#define stream chunk
chunk = 1024
wav_output_filename = './logs/test1.wav'
#open a wav format music
f = wave.open(wav_output_filename,"rb")
#instantiate PyAudio
p = pyaudio.PyAudio()
#open stream
stream = p.open(format = p.get_format_from_width(f.getsampwidth()),
                channels = f.getnchannels(),
                rate = f.getframerate(),
                output = True)
#read data
data = f.readframes(chunk)

#play stream
while data:
    stream.write(data)
    data = f.readframes(chunk)

#stop stream
stream.stop_stream()
stream.close()

#close PyAudio
p.terminate()
#%%
# %%
import glob
from pathlib import Path
timestamp_format = '%Y-%m-%d %H:%M:%S'
soundfile_format = '%Y%m%d%H%M'
soundrecord_directory = '/mnt/share/DKF/SoundRecord'  # reverse slashes
temp_directory = r'D:\Temp'

# %%
sound_files = list(reversed(sorted(glob.glob(str(Path(soundrecord_directory, '*nsrt.wav'))))))
print("sound files of length: {0:d}".format(len(sound_files)))
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%