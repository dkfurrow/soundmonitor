<h1 style="text-align:center">SoundMonitor: An Application for the <br /> <a href="https://convergenceinstruments.com/product/sound-level-meter-data-logger-with-type-1-microphone-nsrt_mk3-dev/" target="_blank">NSRT_mk3_Dev</a> Sound Level Meter</h1>

##Introduction:
The [NSRT_mk3_Dev](https://convergenceinstruments.com/product/sound-level-meter-data-logger-with-type-1-microphone-nsrt_mk3-dev/) Sound Level Meter Data Logger from [Convergence Instuments](https://convergenceinstruments.com/) is a variant of their [NSRT_mk3](https://convergenceinstruments.com/product/sound-level-meter-data-logger-with-type-1-microphone-nsrt_mk3/) series of of sound level data loggers, specifically designed to allow for control of the device from any computer that supports the CDC (Communication) USB class--i.e. Windows, Linux, and Mac. Convergence has conveniently published the [com protocol](https://convergenceinstruments.com/pdf/NSRT_mk3_Com_Protocol.pdf) for this device.  This com protocol is implemented in a [python package](https://github.com/xanderhendriks/nsrt-mk3-dev) available in [pypi](https://pypi.org/project/nsrt-mk3-dev/), authored by [Xander Hendriks](https://github.com/xanderhendriks).

The [NSRT_mk3](https://convergenceinstruments.com/product/sound-level-meter-data-logger-with-type-1-microphone-nsrt_mk3/) series is a sound meter of type I precision capable of measuring decibel levels as real-time exponentially-averaged levels “L”, and integrated L<sub>EQ</sub>s, at a user-specified response time [(i.e. 'fast' or 'slow')](https://www.acoustic-glossary.co.uk/time-weighting.htm). This meter can implement standard frequency weighting curves (A, C, or Z), is factory calibrated (with Manufacturer’s Certificate of Calibration provided), and is capable of being calibrated against any [standard 94dB source](https://convergenceinstruments.com/product/sound-calibrator-ca114/) which will accommodate a 1/2" microphone.

The [NSRT_mk3_Dev](https://convergenceinstruments.com/product/sound-level-meter-data-logger-with-type-1-microphone-nsrt_mk3-dev/) is also capable of acting as a usb-compatible microphone if that [option](https://convergenceinstruments.com/product/audio-usb-interface-option/) is specified with the manufacturer.  This option allows to device to stream a mono audio signal, similar to any other usb microphone, except the pressure signal is calibrated in Pa and weighted by the selected weighting function (A, C or Z).

This project utilizes the nsrt-mk3-dev package, along with [PyAdio](https://pypi.org/project/PyAudio/) and a number of other commonly utilized packages to implement a complete framework for managing the NSRT_mk3_Dev as *both* a sound level meter and microphone, continuously storing a series of sound level measurements and sound files in a configuration specified by the user. The use case for this application is to create a continuous data set of sound pressure readings and sound recordings which can then be subjected to further analysis e.g. for compliance against an industrial standard, compliance with legal noise ordinances, identification of anomalous sound patterns, or other analysis.

##Structure: 

The project has 3 main modules which run from the command line:

1. `metermanager.py`: runs sound meter and manages sound pressure level recording and storage per a named config file.
2. `mikemanager.py`: runs microphone and manages sound recording and storage per a named config file 
3. `datatablecreate.py`: (if desired) creates a set of database tables in MySql to allow for storage of soundmeter data and metadata.

The project has 4 supporting modules:

1. `logmanager.py`manages logging, allowing for logging output to console, text file, database, and email.
2.  `dbinfo.py` handles database connection and saving data to tables
3.  `datamanager.py` handles saving of sound meter data from `metermanager.py`.  Two `DataManager` implementations are included, to save sound data to database and to csv file.  With respect to database connections, *the implementations code assumes availability of the specified host*.  If other data connections are needed (e.g. AWS, MQTT Broker), other `DataManager` implementation could be written.
4.  `datatablecreate.py` handles the creation of mysql database tables expected by `DBDataManager` (the `DataManager` subclass which writes SoundMonitor data to mysql tables. 

###Configuration Files:

There are 3 configuration files, one for database connections, one for `metermanager.py`, one for `mikemanager.py`. They are all configured to be [yaml](https://yaml.org/) files:

**Database:**

---<br />
connection-data:<br />
&emsp;pi1-environ-nsrt: <span style="color:grey"> # alias refers to a full set of connection info</span><br />
&emsp;&emsp;hostname: '192.168.1.221' <span style="color:grey"> # host machine for mysql database</span><br />
&emsp;&emsp;port: '3306' <br />
&emsp;&emsp;db: 'environ' <br />
&emsp;&emsp;user: 'user1' <br />
&emsp;&emsp;passwd: 'password1' <br />
&emsp;&emsp;table-name: 'nsrt_data' <br />
&emsp;localhost-environ-nsrt: <br />
&emsp;&emsp;hostname: 'localhost' <br />
&emsp;&emsp;port: '3306' <br />
&emsp;&emsp;db: 'environ' <br />
&emsp;&emsp;user: 'user2' <br />
&emsp;&emsp;passwd: 'password2' <br />
&emsp;localhost-admin-process_logs: <span style="color:grey"> # here we include a database for logging info</span><br />
&emsp;&emsp;hostname: 'localhost' <br />
&emsp;&emsp;port: '3306' <br />
&emsp;&emsp;db: 'admin' <br />
&emsp;&emsp;table-name: 'process_logs' <br />
&emsp;&emsp;user: 'user3' <br />
&emsp;&emsp;passwd: 'password3' <br />

**SoundMonitor**

---<br />
logger-info:<br />
&emsp;logger-name: "soundmonitor"<span style="color:grey"> # name of logger also names file for logging</span><br />
&emsp;filehandler-data:<span style="color:grey"> # filehandler location, level</span><br />
&emsp;&emsp;include: true<br />
&emsp;&emsp;level: "INFO"<br />
&emsp;&emsp;log-Location: "/home/user1/scripts/logs"<br />
&emsp;gmailhandler-data:<br /><span style="color:grey"> # can include a gmail handler for critical errors...</span><br />
&emsp;include: false<br />
&emsp;dbhandler-data:<span style="color:grey"> # or a database handler if desired...</span><br />
&emsp;&emsp;include: true<br />
&emsp;&emsp;level: 'INFO'<br />
&emsp;&emsp;db-configfile: 'SampleDBaseConfig.yaml'<br />
&emsp;&emsp;db-target-alias: 'localhost-admin-process_logs'<br />
soundmeter-info:<br /><span style="color:grey"> # all information bearing on sound meter parameters and measurement</span><br />
&emsp;device-port: '/dev/ttyACM0'<span style="color:grey"> # found via soundmonitor module or <code>lsusb</code></span><br />
&emsp;meter-id: 0<span style="color:grey"> # id for meter meta information below</span><br />
&emsp;measurement-frequency: 1.0<span style="color:grey"> # measurement frequency in seconds</span><br />
&emsp;run_mins: ~<span style="color:grey"> # minutes to run, null (~) if continuous</span><br />
&emsp;weighting: 'DB_A'<span style="color:grey"> # or 'DB_C', 'DB_Z'</span><br />
&emsp;freq: 48000<span style="color:grey"> # or 32000</span><br />
&emsp;tau: 1.0<span style="color:grey"> # timespan for 'l' measurement (corresponds to 'fast', 'slow', etc)</span><br />
&emsp;data-manager: 'DBDataManager'<span style="color:grey"> # or CSVDataManager, can add other implementations</span><br />
&emsp;db-target-alias: 'localhost-environ-nsrt'<span style="color:grey"> # must be found in database named config file</span><br />
&emsp;db-configfile: 'SampleDBaseConfig.yaml'<br />
&emsp;meta-entry: <span style="color:grey"> # meta information associated with meter placement</span><br />
&emsp;&emsp;station_name: 'test meter'<br />
&emsp;&emsp;station_location: 'location1'<br />
&emsp;&emsp;station_height_m: 5<br />
&emsp;&emsp;modified_by: 'user2'<br />
&emsp;&emsp;modified_time: 'now'<br />
&emsp;csv-location: './logs' <span style="color:grey"> # for use if CSVDataManager is employed</span><br />
&emsp;csv-filename: 'nsrt.csv'<br />

**SoundRecorder**

---
logger-info:<span style="color:grey"> # same logging info as above</span><br />
&emsp;logger-name: "soundrecorder"<br />
&emsp;filehandler-data:<br />
&emsp;&emsp;include: true<br />
&emsp;&emsp;level: "INFO"<br />
&emsp;&emsp;log-Location: "/home/user1/scripts/logs"<br />
&emsp;gmailhandler-data:<br />
&emsp;include: false<br />
&emsp;dbhandler-data:<br />
&emsp;&emsp;include: false<br />
soundrecorder-info:<br />
&emsp;run-minutes: ~<span style="color:grey"> # number of minutes to run or ~ if continuous</span><br />
&emsp;device-index: 6<span style="color:grey"> # device index (can be found using the mikemanager 'check' function</span><br />
&emsp;format: 8<span style="color:grey"> # inputs to PyAudio stream</span><br />
&emsp;sample-rate: 48000<span style="color:grey"> # inputs to PyAudio stream</span><br />
&emsp;chunk: 1000<span style="color:grey"> # inputs to PyAudio stream</span><br />
&emsp;channels: 1<span style="color:grey"> # inputs to PyAudio stream</span><br />
&emsp;input: true<span style="color:grey"> # inputs to PyAudio stream</span><br />
&emsp;delete-old: false <span style="color:grey"> # for testing, if true, deletes all files older than 10 minutes</span><br />
&emsp;output-name: "nsrt" <span style="color:grey"> # name of ourput file (appended to YYYYmmddHHMMSS string, e.g. 202101152348nsrt.wav)</span><br />
&emsp;dest-dir: '/mnt/share/user2/SoundRecord'<span style="color:grey"> # where to save the audio files</span><br />
&emsp;network-share: '//192.168.1.281/shared'<span style="color:grey"> # if network share is used, where to find it</span><br />
&emsp;local-mount: '/mnt/share'<span style="color:grey"> # if network share is used, where it is mounted</span><br />
&emsp;credentials-file: '/home/user2/.smbcredentials'<span style="color:grey"> # if network share is used, where are credentials</span><br />

##Implementation

This project has been tested in linux only, and assumes a python installation of version 3.8.8 or higher.  To implement:

1. unzip or `git clone` project to convenient folder
2. The PyAudio library necesary for sound recording requires installation of the portaudio library development package (portaudio19-dev) and the python development package (python-all-dev).  Please follow the instructions to install these packages for your operating system as noted [here](http://people.csail.mit.edu/hubert/pyaudio/).  Specific instruction to build PortAudio for the various operating systems can be found [here](http://www.portaudio.com/docs/v19-doxydocs/compile_cmake.html)  .
3. Install python libraries from requirements.txt `pip install -r /path/to/requirements.txt`
4. If using the mysql database options, install mysql locally or obtain connection information to a mysql database on a remote computer. Database tables will be installed to configured database on first use.
5. Parameterize configuration files above as needed.
6. Run modules from command line as detailed below.    
    
## Command line arguments, outputs

The two operative modules are `sountmonditor.py`and `soundrecorder.py`. The usages of these two modules is discussed below.  Since different computers or development boards may assign different parameters to the NSRT_mk3_Dev when it is plugged into the usb port, we discuss how to use the modules to 'find' the NSRT_mk3_Dev in the linux operating system.

###soundmonitor.py

running `python soundmonitor.py --help` yields the following:

<pre>usage: soundmonitor [-h] [--config_file CONFIG_FILE] [--check_serial]

Run NSRT sound meter, save results

optional arguments:
  -h, --help            show this help message and exit
  --config_file CONFIG_FILE
                        config file to run
  --check_serial
</pre>

running the `--check_serial` option (on a laptop running linux mint, with NSRT_mk3_Dev connected) yielded the following :

<pre>checking serial ports...
{&apos;description&apos;: &apos;NSRT_mk3_Dev - NSRT_mk3-Com&apos;,
 &apos;device&apos;: &apos;/dev/ttyACM0&apos;,
 &apos;device_path&apos;: &apos;/sys/devices/pci0000:00/0000:00:14.0/usb1/1-3/1-3:1.1&apos;,
 &apos;hwid&apos;: &apos;USB VID:PID=0A59:0143 LOCATION=1-3:1.1&apos;,
 &apos;interface&apos;: &apos;NSRT_mk3-Com&apos;,
 &apos;location&apos;: &apos;1-3:1.1&apos;,
 &apos;manufacturer&apos;: &apos;Convergence Instruments&apos;,
 &apos;name&apos;: &apos;ttyACM0&apos;,
 &apos;pid&apos;: 323,
 &apos;product&apos;: &apos;NSRT_mk3_Dev&apos;,
 &apos;serial_number&apos;: None,
 &apos;subsystem&apos;: &apos;usb&apos;,
 &apos;usb_device_path&apos;: &apos;/sys/devices/pci0000:00/0000:00:14.0/usb1/1-3&apos;,
 &apos;usb_interface_path&apos;: &apos;/sys/devices/pci0000:00/0000:00:14.0/usb1/1-3/1-3:1.1&apos;,
 &apos;vid&apos;: 2649}
{&apos;vendorId&apos;: &apos;0A59&apos;, &apos;productId&apos;: &apos;0143&apos;}
exiting...
</pre>

So the `device-port` entry in the appropriate config file is `/dev/ttyACM0`, for this particular device.

###soundrecorder.py

running the `help` option in the same manner as above yields:

<pre>usage: soundrecorder [-h] [--config_file CONFIG_FILE] action

Check PyAudio devices, Manage NSRT Microphone

positional arguments:
  action                enter either run or check

optional arguments:
  -h, --help            show this help message and exit
  --config_file CONFIG_FILE
                        config file to run
</pre>

So in this case, we use the `check` argument, i.e. `python soundrecorder.py check` to get a list of audio devices recognized by pyaudio:

<pre>index: 0, name:HDA Intel PCH: CX20753/4 Analog (hw:0,0)
index: 1, name:HDA Intel PCH: HDMI 0 (hw:0,3)
index: 2, name:HDA Intel PCH: HDMI 1 (hw:0,7)
index: 3, name:HDA Intel PCH: HDMI 2 (hw:0,8)
index: 4, name:HDA Intel PCH: HDMI 3 (hw:0,9)
index: 5, name:HDA Intel PCH: HDMI 4 (hw:0,10)
index: 6, name:NSRT_mk3_Dev: USB Audio (hw:1,0)
index: 7, name:sysdefault
index: 8, name:front
index: 9, name:surround40
index: 10, name:surround51
index: 11, name:surround71
index: 12, name:hdmi
index: 13, name:samplerate
index: 14, name:speexrate
index: 15, name:pulse
index: 16, name:upmix
index: 17, name:vdownmix
index: 18, name:dmix
index: 19, name:default
</pre>

and we see that the microphone associated with the NSRT_mk3_Dev is at index '6'.  Therefore, the appropriate `device-index` entry in the config file for soundrecorder is 6. 

##Expected Result
For `SoundMonitor`, we observe a continuous stream of sound data written either to a csv file or a set of database tables, in accordance with the configuration file entries.  The module writes in batches, one batch every calendar minute, with the number of entries in each minute determined by the `measurement-frequency` entry (effectively, the length of time in seconds between queries of the sound meter for data).  As noted in the [NSRT_mk3_Dev](https://convergenceinstruments.com/product/sound-level-meter-data-logger-with-type-1-microphone-nsrt_mk3-dev/) user manual, the `measurement-frequency` entry also sets the time period associated with the 'L<sub>EQ</sub>' value received from the meter.  In contrast, the period of time associated with the 'L' value is explicitly set in the config file by the `tau` entry.<br /><br />**database structure:**  if the DBDataManager is utilized, data are stored in 3 tables: `nsrt_data` holds the time series of sound and temperature data, with reference to selected meter parameters in `nsrt_params` and meta data in `nsrt_meta`. **Example output:**<br/>
<pre>
<b><u>nsrt_data</u></b>
id                                 60
timestamp  2022-02-14 20:44:59.002266
lavg                            35.09
leq                             35.06
temp_f                          67.29
params_id                           0
nsrt_id                             0
</pre>
<pre>
<b><u>nsrt_params</u></b>
id                                        0
tau                                    1.00
wt                                     DB_A
freq                                  48000
serial_number        AnL+rP2wcV+1AjPCwwhxPD
firmware_revision                      1.30
date_of_birth           2021-07-09 09:44:56
date_of_calibration     2021-12-11 13:17:48
</pre>
<pre>
<b><u>nsrt_meta</u></b>
id                                  0
station_name                     test
station_location               office
station_height_m                   15
modified_by                   dfurrow
modified_time     2022-02-14 20:43:04
</pre>

For `SoundRecorder`, we observe a sequence of 'wav' files written to the location specified in the config file. The file format is YYYYmmddHHMMSS**name**, where **name** is specified in the `output-name` entry in the config file.  For example, where **name** is 'nsrt', then the minute *ending* 11:48:00 PM on Jan 15, 2021 will be named *202101152348nsrt.wav*.

##Final Notes

I generally run these modules as a service from a development board, such as a raspberry pi, routing the soundmonitor output to an internal mysql database, and the generated 'wav' soundfiles to available network storage.  [Here](https://websofttechs.com/tutorials/how-to-setup-python-script-autorun-in-ubuntu-18-04/) is a good basic description of how to setup a service from a python script--a basic search will yield many others.  Your use case may differ--in which case, the code released here might form a useful base for your own sound monitoring project.

