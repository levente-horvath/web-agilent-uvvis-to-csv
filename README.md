# web-uv2csv
A simple web UI added for UV-vis conversion to csv. Forked from https://github.com/dd-hebert/agilent-uvvis-to-csv.

Currently supports **.KD** and **.SD** UV-vis binary file types.

## Requirements
```sh
pip install -r requirements.txt
```
## To start the webserver
```sh
python app.py
```

## Changing The Wavelength Range
By default, the script assumes your spectrometer captures data from **190 nm to 1100 nm**. If the range of wavelengths your spectrometer records is different than this, you can set the wavelength range by adding a single keyword argument ``wavelength_range`` to the ``UVvisFile`` object constructor at the bottom of the script:

```python
UVvisFile(path, export_csv=True, wavelength_range=(min, max))
```
Running the script with an incorrect wavelength range might lead to unexpected results and messed-up looking spectra. It seems that both the Agilent 8453 and 8454 spectrometer models only capture data from 190 nm to 1100 nm, so the default setting should work fine for most cases. However, if needed, this setting can be adjusted as shown above. In the future, I may add a feature that automatically detects the correct wavelength range.

## Disclaimer
This script has only been tested on files from a small number of different versions of the Agilent UV-vis Chemstation software. Therefore, binary files from other versions of UV-vis Chemstation, different spectrometer setups, or custom methods may not work.

**Known Supported Chemstation Versions:**
- B.05.02 [16]
- A.08.03 [71]
