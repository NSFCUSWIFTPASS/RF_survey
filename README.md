# Radio Frequency (RF) Noise Survey

## Overview

The RF Noise Survey is an open source tool developed by the WIRG lab at the University of Colorado Boulder to measure baseline radio frequency (RF) interference. This tool is designed to run on a Raspberry Pi 4 connected to an Ettus Research B200mini USRP (Software Defined Radio). It aids in understanding and improving RF spectrum sharing for both communications and scientific purposes.

> **Key Features:**
> - **Command Line Surveys:** Run surveys via CLI using Python scripts.
> - **Graphical Interface:** A GUI is available (in the `GUI/` folder) for Mac and Linux.
> - **Monitoring:** Tools in the `monitoring/` folder help with system health and logging.
> - **Data Processing:** Measures power and spectral characteristics to analyze RF interference.

## Quick Start Guide
Welcome to the RF Noise Survey, an open source tool for measuring baseline radio frequency interference. These surveys are designed to be run on a Raspberry Pi 4 connected to an Ettus Research B200mini Universal Software Radio Peripheral (USRP) Software Defined Radio (SDR).

The code can be downloaded with 
```
pip install rf-survey==0.1
```

These surveys can be run from the command in Linux or via the RF Survey GUI. An example command line basic survey is:
```
nohup python3 /home/pi/rf_survey/sweeps.py -f1 915000000 -b 26000000 -s 2                                                                                                                                  6000000 -g 35 -r 1 -t 10 -c 0  -o ucb_db_test -gcs 40N105W &
```

The GUI can be run on Mac or Linux, not currently supported for Windows:
```
cd RF_survey
conda create -n GUI
conda activate GUI
cd GUI
python rf_survey_gui_v4.4.1.py
```

## Introduction
Developed by the WIRG lab at the University of Colorado Boulder under NSF [SWIFT](https://new.nsf.gov/funding/opportunities/spectrum-wireless-innovation-enabled-future/505858), the RF noise survey measures RF interference in order to better enable active and passive spectrum sharing. As described in this paper published at IEEE Aerospace 2023, ["Testbed for Radio Astronomy Interference Characterization and Spectrum Sharing Research"](https://www.aeroconf.org/cms/content_attachments/75/download), this code has been deployed and tested at the [Hat Creek Radio Observatory](https://www.seti.org/hcro). 

![An image overview of the RF Baseline Noise Survey Collection.](/rf_survey/images/RF_Noise_Survey.png)

Figure 1-1 depicts a conceptual overview of the RF Baseline Noise Survey Collection. A) An illustration of the Fourier decomposition of a signal in the time domain, to the frequency domain. The filled blue area represents the baseline noise-floor - and the goal of the data collection is to establish the power levels of this floor in both low energy and high noise environments. B) The noise floor is influenced by a multitude of sources: from natural sources of RF Energy such as lightning and cosmic noise to C) intentional and unintentional manmade noise from various electrical devices. . D) The RF Baseline Noise Survey System architecture consists of multiple software defined radio nodes used for the collection of RF spectrum data and a central server for processing and storing the incoming data. E) Finally, local topography has a significant effect on signal propagation and therefore the noise floor. 

The primary methods of measuring RF interference with this survey are through power and spectral kurtosis collected from the Streamer class.

## Code Structure
The repository is divided into several key directories:

rf_survey/: Contains the core Python modules for the RF survey tool.
GUI/: Contains the graphical user interface script.
monitoring/: Includes scripts for system monitoring, logging, and alerting.

## Modules
| Module              | Description                                                                                                                                                          |
|---------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `sweeps.py`         | Entry point for command line surveys. Parses arguments, initializes surveys, and orchestrates data collection from the SDR.                                           |
| `rf_survey.py`      | Main module that integrates various functionalities of the survey. Coordinates data collection, processing, and saving of results.                                   |
| `Cronify.py`        | Provides scheduling or timing-related functionalities for periodic RF surveys.                                                                                    |
| `GracefulKiller.py` | Implements signal handling for graceful termination of the survey process, ensuring resources are cleaned up properly on exit.                                      |
| `Logger.py`         | Contains logging functionality to record events, errors, and informational messages during survey execution.                                                        |
| `Restoration.py`    | Handles restoration or recovery processes, possibly to reinitialize system settings or recover from interruptions during data collection.                           |
| `hardware.py`       | Manages interactions with hardware components, including the USRP SDR, and handles low-level configurations and commands.                                           |
| `kill.py`           | Provides utilities to forcefully stop or manage running processes related to the survey.                                                                            |
| `wr_boot.py`        | Likely handles initialization or bootstrapping of the survey environment, ensuring all necessary components are correctly configured before starting the survey. |
| `wr_poll.py`        | Polls hardware or system metrics during survey operation, providing real-time status updates or adjustments as needed.                                                |

## Methods
| Method/Function                 | Module             | Description                                                                                                             |
|---------------------------------|--------------------|-------------------------------------------------------------------------------------------------------------------------|
| `main()`                        | `sweeps.py`        | Initializes the survey, parses command-line arguments, and starts the RF data collection process.                        |
| `start_survey()`                | `rf_survey.py`     | Coordinates the overall survey workflow by integrating hardware initialization, data collection, and processing.         |
| `schedule_cron()`               | `Cronify.py`       | Schedules periodic survey runs or tasks using cron-like functionalities.                                               |
| `handle_signals()`              | `GracefulKiller.py`| Captures system signals (e.g., SIGINT) to gracefully terminate the survey and perform cleanup.                           |
| `log_event(message)`            | `Logger.py`        | Logs events and error messages during survey execution.                                                               |
| `restore_state()`               | `Restoration.py`   | Restores system or survey state after an interruption or unexpected termination.                                        |
| `configure_hardware()`          | `hardware.py`      | Sets up and configures the SDR hardware for data collection, including frequency and bandwidth settings.                |
| `terminate_process()`           | `kill.py`          | Terminates running survey processes safely.                                                                            |
| `initialize_boot()`             | `wr_boot.py`       | Initializes survey parameters and hardware configurations during system startup.                                       |
| `poll_status()`                 | `wr_poll.py`       | Continuously polls hardware and system status to provide real-time updates and ensure optimal operation.                 |
