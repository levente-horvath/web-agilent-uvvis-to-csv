# uv2csv
A simple script for converting Agilent 845x Chemstation UV-Vis binary files (**.KD** or **.SD** formats) to .csv format.

Do you have **.KD** or **.SD** UV-Vis binary files but no access to the Agilent 845x UV-Vis Chemstation software? Are your **.KD** files massive and contain thousands of spectra? This script will automatically read and convert your **.KD** or **.SD** files to .csv format (and it's significantly faster than exporting .csv files directly from the Agilent Chemstation software!). Exports thousands of spectra in seconds!

Currently supports **.KD** and **.SD** binary file types.

## Using This Script
To use this script, simply run it from the command line:

```sh
python uv2csv.py
```
Then provide a file path when prompted.

## Where .CSV Files Are Exported
The specified **.KD** or **.SD** binary file is read and UV-Vis spectra are automatically exported as .csv files. 
- **.KD files:** .csv files are exported to a folder named ``self.name`` in ``self.path``. 
- **.SD files:** a single .csv file named ``self.name`` is exported to ``self.path``.

Here ``self.name`` is the name of the binary file (without the file extension) and ``self.path`` is the file path where the binary file is located.

## Changing The Wavelength Range
By default, the script assumes the spectrometer captures data from **190 nm to 1100 nm**. If the range of wavelengths your spectrometer records is different than this, you can set the wavelength range by adding a single keyword argument ``wavelength_range`` to the function on line 39:

```python
# Line 39
self.spectra = self.read_binary() # Default wavelength range (190 to 1100 nm).
```

```python
# Line 39
self.spectra = self.read_binary(wavelength_range=(min,max)) # Set a different wavelength range from min to max (in nm).
```

## Requirements
You must have the [pandas](https://pandas.pydata.org/) python package installed to use this script.
