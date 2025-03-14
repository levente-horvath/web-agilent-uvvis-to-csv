"""
A web application to convert Agilent 845x Chemstation UV-vis files to .csv format.
Supports .KD and .SD file types.

Version 0.1.11
Created by David Hebert, Webapp adaptation by Grok
"""

from flask import Flask, request, send_file, render_template_string, Response
from werkzeug.utils import secure_filename
import os
from struct import iter_unpack
from pathlib import Path
import pandas as pd
import zipfile
import io

app = Flask(__name__)

# Original script code (UVvisFile class and supporting functions remain largely unchanged)
# [Insert the UVvisFile class and supporting functions from the original script here]
# I'll only show the modified/new parts for brevity


"""
A simple script to convert Agilent 845x Chemstation UV-vis files to .csv format.

To use this script, simply run it from the command line then provide a file
path. Currently supported UV-vis file types are .KD and .SD files.

Version 0.1.10
Created by David Hebert

"""

SUPPORTED_FILE_TYPES = ['.KD', '.SD']
ENCODINGS = [
    'latin1',
    'windows-1252',
    'latin9',
    'cyrillic',
    'windows-1251',
    'latin2',
    'latin5',
    'sjis',
    'korean',
    'gb18030',
    'big5',
    'utf16'
]


class UVvisFile:
    """
    A UVvisFile object.

    Supported file types are .KD and .SD. Upon creation of a `UVvisFile` \
    object, the specified .KD or .SD binary file is read and unpacked into a \
    :class:`pandas.DataFrame`.

    Attributes
    ----------
    spectrum_bytes_length : int
        The length (in bytes) of each spectrum based on the range \
        of wavelengths captured by the detector.
    spectra : list[pandas.DataFrame]
        A list of :class:`pandas.DataFrame` containing the UV-vis spectra.
    samplenames : list[str]
        A list of sample names as strings.
    """

    def __init__(self, path: str, export_csv: bool = False,
                 wavelength_range: tuple = (190, 1100)) -> None:
        """
        Initialize a :class:`UVvisFile` object and read a UV-vis binary file.

        Parameters
        ----------
        path : str
            The file path to a UV-vis binary file (.KD or .SD format).
        export_csv : bool
            True or False. If True, automatically export .csv files upon \
            creation of the :class:`UVvisFile` object. Default is False \
            (.csv files not automatically exported.)
        wavelength_range : tuple[int, int]
            Set the range of wavelengths (in nm) recorded by the detector \
            (min, max). Default value is (190, 1100).
        """
        self._path = Path(path)
        self.path = str(self._path)
        self.wavelength_range = sorted(map(int, wavelength_range))
        self.spectrum_bytes_length = self._spectrum_bytes_length()
        self.spectra, self.samplenames = self.read_binary()

        if export_csv:
            self.export_csv()

    def _spectrum_bytes_length(self) -> int:
        # Data is 8 hex characters for each wavelength.
        return (self.wavelength_range[1] - self.wavelength_range[0] + 1) * 8

    def read_binary(self) -> tuple[list[pd.DataFrame], list[str]]:
        """
        Read a .KD or .SD file and extract spectra and sample names.

        Returns
        -------
        spectra : list[pandas.DataFrame]
            A list of :class:`pandas.DataFrame` containing the UV-vis
            spectra.
        samplenames : list[str]
            A list of strings with sample names.
        """
        ext = self._path.suffix.upper()

        print(f'Reading {ext} file...')
        with open(self.path, 'rb') as binary_file:
            file_bytes = binary_file.read()

        spectra = self._read_spectra(file_bytes)

        if ext == '.SD':
            samplenames = self._read_samplenames(file_bytes, len(spectra))
            return spectra, samplenames

        return spectra, [''] * len(spectra)

    def _read_spectra(self, file_bytes: bytes) -> list[pd.DataFrame]:
        """
        Read the spectra from a .KD or .SD file.

        Parameters
        ----------
        file_bytes : bytes
            The raw bytes of the binary file.

        Raises
        ------
        Exception
            Raises an exception if no spectra are found.

        Returns
        -------
        spectra : list[pandas.DataFrame]
            A list of :class:`pandas.DataFrame` containing the UV-vis
            spectra.
        """
        header, spacing = self._find_absorbance_header(file_bytes)
        wavelengths = pd.Series(range(self.wavelength_range[0], self.wavelength_range[1] + 1))

        spectra = [
            pd.DataFrame({'Wavelength (nm)': wavelengths, 'Absorbance (AU)': [val for val, in iter_unpack('<d', spectrum)]})
            for spectrum in self._extract_data(file_bytes, header, spacing)
        ]

        if spectra == []:
            raise Exception('Error parsing file. No spectra found.')

        return spectra

    def _find_absorbance_header(self, file_bytes: bytes) -> tuple[bytes, int]:
        """
        Search the binary file for the appropriate absorbance data header.

        Parameters
        ----------
        file_bytes : bytes
            The raw bytes of the binary file.

        Raises
        ------
        Exception
            Raises an exception if no absorbance data headers can be found.

        Returns
        -------
        header : bytes
            The absorbance data header as a hex string.
        spacing : int
            The spacing between the header and the beginning of the actual data.
        """
        # Each header contains its hex string and the spacing that follows it.
        headers = {
            '( A U ) ': (b'\x28\x00\x41\x00\x55\x00\x29\x00', 17),
            '(AU) ': (b'\x28\x41\x55\x29\x00', 5)
        }

        for _, (header, spacing) in headers.items():
            if file_bytes.find(header, 0) != -1:
                return header, spacing

        raise Exception('Error parsing file. No absorbance data headers could be found.')

    def _read_samplenames(self, file_bytes: bytes, num_samples: int) -> list[str]:
        """
        Read the sample names from a .SD file.

        Parameters
        ----------
        file_bytes : bytes
            The raw bytes of the binary file.
        num_samples : int
            The number of samples or spectra in the .SD file.

        Returns
        -------
        samplenames : list[str]
            A list of sample names as strings.
        """
        header, spacing, end_char = self._find_samplename_header(file_bytes)
        if header is None:
            return [''] * num_samples

        samplenames = [
            decode_with_fallback(samplename)
            for samplename in self._extract_data(file_bytes, header, spacing, end_char)
        ]

        if len(samplenames) < num_samples:
            remainder = num_samples - len(samplenames)
            blank_names = [''] * remainder
            samplenames.extend(blank_names)

        return samplenames

    def _find_samplename_header(self, file_bytes: bytes) -> tuple[bytes, int, bytes] | tuple[None, None, None]:
        """
        Search the binary file for the appropriate sample name header.

        Returns `(None, None, None)` if no header is found.

        Parameters
        ----------
        file_bytes : bytes
            The raw bytes of the binary file.

        Returns
        -------
        header : bytes or None
            The sample name header as a hex string.
        spacing : int or None
            The spacing between the header and the beginning of the actual data.
        end_char : bytes or None
            The end-of-data termination character.
        """
        # Each header contains its hex string, spacing, and termination character.
        headers = {
            'S a m p l e N a m e ': (
                b'\x53\x00\x61\x00\x6D\x00\x70\x00\x6C\x00\x65'
                b'\x00\x4E\x00\x61\x00\x6D\x00\x65\x00',
                28,
                b'\x09'
            ),
            '(`DataType': (
                b'\x28\x60\x44\x61\x74\x61\x54\x79\x70\x65',
                33,
                b'\x02'
            )
        }

        for _, (header, spacing, end_char) in headers.items():
            if file_bytes.find(header, 0) != -1:
                return header, spacing, end_char

        return None, None, None

    def _extract_data(self, file_bytes: bytes, header: bytes,
                      spacing: int, end_char: bytes | None = None) -> list[bytes]:
        """
        Extract relevant data from a bytes string, such as spectra or sample names.

        Parameters
        ----------
        file_bytes : bytes
            The raw bytes of the binary file.
        header : bytes
            The header which precedes the data of interest.
        spacing : int
            The spacing between the header and the data.
        end_char : bytes | None, optional
            A termination character for the data, by default None.

        Returns
        -------
        out : list[bytes]
            A list of bytes strings of the relevant data.
        """
        position = 0
        out = []

        if end_char:
            def get_end_idx(file_bytes, start_idx):
                end_idx = file_bytes.find(end_char, start_idx)
                return end_idx if end_idx != -1 else None

        else:
            def get_end_idx(file_bytes, start_idx):
                return start_idx + self.spectrum_bytes_length

        while True:
            header_idx = file_bytes.find(header, position)
            if header_idx == -1:
                break

            start_idx = header_idx + spacing
            end_idx = get_end_idx(file_bytes, start_idx)

            if end_idx is None:
                break

            out.append(file_bytes[start_idx:end_idx])

            position = end_idx

        return out

    def export_csv(self) -> None:
        """
        Export spectra as .csv files.

        When exporting multiple spectra, .csv files are exported to a \
        folder in same directory as the parent .KD or .SD file. When \
        exporting with a single spectrum, a single .csv file is \
        exported to the same directory as the parent .KD or .SD file.

        For .SD files, sample names (if present) will be appended to the \
        exported filenames.
        """
        pardir = self._path.parent
        base_filename = self._path.stem
        print('Exporting .csv files...')

        def get_unique_path(base_path: str, ext: str = '') -> str:
            n = 1
            unique_path = base_path

            while pardir.joinpath(unique_path).with_suffix(ext).exists():
                unique_path = base_path + f' ({n})'
                n += 1

            return unique_path + ext

        def export_multiple_spectra(output_dir: Path) -> str:
            output_dir.mkdir()
            digits_prefix = len(str(len(self.spectra)))

            for i, (spectrum, samplename) in enumerate(zip(self.spectra, self.samplenames), start=1):
                filename = f'{str(i).zfill(digits_prefix)}'
                if samplename:
                    filename += f' - {samplename}'

                spectrum.to_csv(
                    path_or_buf=output_dir.joinpath(f'{filename}.csv'),
                    index=False
                )

            return output_dir

        def export_single_spectrum(filename: str) -> str:
            if self.samplenames[0]:
                filename += f' - {self.samplenames[0]}'

            filename = get_unique_path(filename, ext='.csv')
            self.spectra[0].to_csv(
                path_or_buf=pardir.joinpath(filename),
                index=False
            )

            return filename

        if len(self.spectra) > 1:
            output_dir = pardir.joinpath(get_unique_path(base_filename))
            out = export_multiple_spectra(output_dir)

        else:
            out = export_single_spectrum(base_filename)

        print(f'Finished export: {out}')


def decode_with_fallback(byte_string: bytes) -> str:
    byte_string = byte_string.replace(b'\x00', b'')

    try:
        return byte_string.decode('utf8')

    except UnicodeDecodeError:
        for encoding in ENCODINGS:
            try:
                return byte_string.decode(encoding)

            except UnicodeDecodeError:
                continue

        return byte_string.decode('utf8', 'replace')


def input_path() -> str:
    """
    Get a user-inputted file path.

    You can exit the input prompt by entering 'q' or alternatively \
    by entering a EOF control character (platform-specific, CTRL+Z \
    on Windows) or keyboard interrupt (CTRL+C on Windows).

    Returns
    -------
    path : str
        A valid path to a .KD or .SD file or an empty string
        if the user exits the input prompt.
    """
    try:
        path = input('Enter a file path or "q" to quit: ')

        if path.lower() == 'q':
            return ''

        path = Path(path)
        if path.is_file() and path.suffix.upper() in SUPPORTED_FILE_TYPES:
            return str(path)

        else:
            print('Invalid file path (must be a .KD or .SD file).')
            return input_path()

    except (EOFError, KeyboardInterrupt):
        return ''







SUPPORTED_FILE_TYPES = ['.KD', '.SD']
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'kd', 'sd'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# HTML template as a string
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>UV-vis File Converter</title>
    <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: auto; }
        .error { color: red; }
        .success { color: green; }
    </style>
</head>
<body>
    <div class="container">
        <div class="jumbotron text-center">
            <h1 class="display-4">UV-vis File Converter</h1>
            <p class="lead">Convert Agilent 845x Chemstation UV-vis files (.KD or .SD) to CSV format</p>
        </div>
        
        <form method="post" enctype="multipart/form-data" class="mb-4">
            <div class="form-group">
                <label for="file">Choose a file</label>
                <input type="file" class="form-control-file" id="file" name="file" accept=".kd,.sd">
            </div>
            <button type="submit" class="btn btn-primary btn-block">Convert</button>
        </form>
        
        {% if error %}
            <div class="alert alert-danger" role="alert">
                {{ error }}
            </div>
        {% endif %}
        {% if success %}
            <div class="alert alert-success" role="alert">
                {{ success }}
            </div>
        {% endif %}
    </div>
    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.5.4/dist/umd/popper.min.js"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    if request.method == 'POST':
        # Check if a file was uploaded
        if 'file' not in request.files:
            return render_template_string(HTML_TEMPLATE, error='No file uploaded')
        
        file = request.files['file']
        
        if file.filename == '':
            return render_template_string(HTML_TEMPLATE, error='No file selected')
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                # Process the file
                uvvis = UVvisFile(filepath)
                
                # If single spectrum, return single CSV
                if len(uvvis.spectra) == 1:
                    output_filename = f"{Path(filename).stem}"
                    if uvvis.samplenames[0]:
                        output_filename += f" - {uvvis.samplenames[0]}"
                    output_filename += ".csv"
                    
                    uvvis.spectra[0].to_csv(filepath, index=False)
                    return send_file(
                        filepath,
                        as_attachment=True,
                        download_name=output_filename
                    )
                
                # If multiple spectra, create zip file
                else:
                    memory_file = io.BytesIO()
                    with zipfile.ZipFile(memory_file, 'w') as zf:
                        digits_prefix = len(str(len(uvvis.spectra)))
                        for i, (spectrum, samplename) in enumerate(zip(uvvis.spectra, uvvis.samplenames), start=1):
                            filename = f'{str(i).zfill(digits_prefix)}'
                            if samplename:
                                filename += f' - {samplename}'
                            filename += '.csv'
                            
                            # Create temporary CSV in memory
                            csv_buffer = io.StringIO()
                            spectrum.to_csv(csv_buffer, index=False)
                            zf.writestr(filename, csv_buffer.getvalue())
                    
                    memory_file.seek(0)
                    return Response(
                        memory_file.getvalue(),
                        mimetype='application/zip',
                        headers={
                            'Content-Disposition': f'attachment;filename={Path(filename).stem}_converted.zip'
                        }
                    )
                    
            except Exception as e:
                return render_template_string(HTML_TEMPLATE, error=f'Error processing file: {str(e)}')
            finally:
                # Clean up uploaded file
                if os.path.exists(filepath):
                    os.remove(filepath)
                    
        return render_template_string(HTML_TEMPLATE, error='Invalid file type. Please upload .KD or .SD file')
    
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(debug=True)