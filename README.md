# Radio Frequency (RF) Noise Survey

## Quick Start Guide
Welcome to the RF Noise Survey, an open source tool for measuring baseline radio frequency interference. These surveys are designed to be run on a Raspberry Pi 4 connected to an Ettus Research B200mini Universal Software Radio Peripheral (USRP) Software Defined Radio (SDR).

These surveys can be run from the command in Linux or via the RF Survey GUI. An example command line basic survey is:

The GUI requires Anaconda to install:
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
