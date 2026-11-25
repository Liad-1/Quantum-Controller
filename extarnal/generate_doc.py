"""
Generates the Word document: confocal_scan_setup.docx
Run this script once to produce the document.

Requires: pip install python-docx
"""

from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "confocal_scan_setup.docx")


def add_heading(doc, text, level=1):
    doc.add_heading(text, level=level)


def add_code_block(doc, code_text):
    """Add a monospace grey-background paragraph for code."""
    para = doc.add_paragraph()
    para.style = doc.styles['Normal']
    run = para.add_run(code_text)
    run.font.name = 'Courier New'
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x20, 0x20, 0x20)
    pPr = para._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), 'F0F0F0')
    pPr.append(shd)
    para.paragraph_format.left_indent = Cm(1)
    return para


def build_document():
    doc = Document()

    # ------------------------------------------------------------------ Title
    title = doc.add_heading('Confocal Scanning Measurement Setup', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(
        'Python-controlled confocal scanner using NI myDAQ, '
        'OIM101 Fast Steering Mirror, Swabian Instruments Pulse Streamer, '
        'and Time Tagger / PicoHarp 300.'
    ).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    # --------------------------------------------------------------- Overview
    add_heading(doc, '1. Overview', level=1)
    doc.add_paragraph(
        'This document describes a confocal scanning microscope setup designed '
        'to image and characterise individual quantum emitters (such as '
        'nitrogen-vacancy (NV) centres in diamond). '
        'The setup collects photoluminescence (PL) maps of a sample surface '
        'by steering a focused laser beam across the sample using a fast '
        'steering mirror (FSM), counting the photons emitted at each position. '
        'At selected pixels, full spin-control pulse sequences can be executed '
        '(ODMR, Rabi, T1, T2) while the beam is stationary.'
    )

    # ------------------------------------------------------------ Hardware
    add_heading(doc, '2. Hardware Components', level=1)

    components = [
        ('OIM101 Fast Steering Mirror (Optics in Motion)',
         'Steers the laser beam in X and Y over the sample. '
         'Accepts ±10 V analog input; full angular range corresponds to '
         'up to 240 µm scan area depending on the objective magnification.'),
        ('NI myDAQ',
         'Provides two analog output channels (ao0, ao1) with ±10 V range '
         'and 16-bit resolution at up to 200 kS/s. '
         'ao0 drives the FSM X axis; ao1 drives the FSM Y axis. '
         'No photon-counting hardware is used on the myDAQ — counting is '
         'handled entirely by the Time Tagger.'),
        ('Swabian Instruments Pulse Streamer 8/2',
         'Generates all fast digital pulse sequences with nanosecond '
         'resolution. '
         'Channel 0 outputs a TTL marker pulse to the Time Tagger at the '
         'start of each pixel measurement. '
         'Channel 1 gates the laser AOM (acousto-optic modulator). '
         'Channel 2 drives the microwave switch for spin control.'),
        ('Time Tagger / PicoHarp 300 (PicoQuant)',
         'Records the arrival time of every photon from the avalanche '
         'photodiode (APD) with picosecond resolution. '
         'A dedicated marker channel receives TTL pulses from the Pulse '
         'Streamer to stamp each pixel boundary in the photon time stream, '
         'allowing photon counts to be assigned to scan positions in '
         'post-processing.'),
        ('Avalanche Photodiode (APD)',
         'Converts single photons into TTL pulses fed to the Time Tagger '
         'photon input channel.'),
    ]

    for name, desc in components:
        p = doc.add_paragraph(style='List Bullet')
        run = p.add_run(name + ': ')
        run.bold = True
        p.add_run(desc)

    # ---------------------------------------------------- Wiring diagram
    add_heading(doc, '3. Signal Wiring', level=1)
    doc.add_paragraph('The hardware is connected as follows:')
    add_code_block(doc,
        "NI myDAQ  ao0  ──────────────────→  OIM101  X input\n"
        "NI myDAQ  ao1  ──────────────────→  OIM101  Y input\n"
        "\n"
        "Pulse Streamer  Ch0  ────────────→  Time Tagger  marker channel\n"
        "Pulse Streamer  Ch1  ────────────→  Laser AOM (gate)\n"
        "Pulse Streamer  Ch2  ────────────→  MW switch\n"
        "\n"
        "APD output  ─────────────────────→  Time Tagger  photon channel\n"
    )

    # ---------------------------------------------------- Measurement flow
    add_heading(doc, '4. Measurement Flow', level=1)
    doc.add_paragraph(
        'The measurement uses a step-and-measure approach: the FSM moves to '
        'each pixel position and holds still while the Pulse Streamer executes '
        'a measurement sequence. Python coordinates all devices sequentially.'
    )

    steps = [
        'Generate raster voltage waveform (see Section 5).',
        'Start myDAQ to output the waveform at the configured clock rate '
        '(e.g. 400 Hz). The FSM follows the voltage and sweeps the beam.',
        'At each pixel, Python calls ps.startNow() to fire the Pulse Streamer '
        'sequence. The first pulse in the sequence is a short TTL marker pulse '
        'sent to the Time Tagger marker channel.',
        'The remaining pulses in the sequence gate the laser and optionally '
        'drive microwave pulses for spin control.',
        'The Time Tagger records all photon arrival times. Marker events '
        'divide the photon stream into per-pixel segments.',
        'After the scan, Python reads the Time Tagger data, counts photons '
        'between consecutive marker events, and assembles the 2D image array.',
        'The image is displayed and saved.',
    ]

    for i, step in enumerate(steps, 1):
        doc.add_paragraph(f'{i}. {step}', style='List Number')

    # Pseudo-code
    doc.add_paragraph()
    doc.add_paragraph('Simplified Python control loop:')
    add_code_block(doc,
        "waveform, x_um, y_um, nx, ny = generate_raster_waveform(...)\n"
        "\n"
        "mydaq_task.write(waveform)          # output scan voltages\n"
        "mydaq_task.start()\n"
        "\n"
        "ps.stream(sequence)                 # load sequence once\n"
        "\n"
        "for ix in range(nx):\n"
        "    for iy in range(ny):\n"
        "        mydaq.set_voltage(x_um[ix], y_um[iy])   # move FSM\n"
        "        time.sleep(0.002)                        # settle\n"
        "        ps.startNow()                            # marker + pulses\n"
        "        counts = timetagger.get_counts()         # read photons\n"
        "        image[ix, iy] = counts\n"
        "\n"
        "plt.imshow(image, extent=[x_um[0], x_um[-1], y_um[0], y_um[-1]])\n"
    )

    # ---------------------------------------------------- Waveform
    add_heading(doc, '5. Raster Waveform Generation', level=1)
    doc.add_paragraph(
        'The function generate_raster_waveform() (scan_waveform.py) produces '
        'a voltage array that the myDAQ outputs on ao0 (X) and ao1 (Y) to '
        'drive the FSM through the scan pattern. '
        'It is a direct translation of the generate_raster_vector() method '
        'from the Bassett Lab MATLAB codebase (FastSteeringMirror.m).'
    )

    add_heading(doc, '5.1  Voltage Calculation', level=2)
    doc.add_paragraph(
        'Physical scan coordinates (in micrometres) are converted to voltages '
        'using the FSM calibration scale factor (µm/V):'
    )
    add_code_block(doc,
        "dV      = step_size / scale\n"
        "start_V = (scan_center - scan_size / 2) / scale\n"
        "end_V   = (scan_center + scan_size / 2) / scale\n"
    )
    doc.add_paragraph(
        'Default scale factors from the lab configuration file '
        '(60x air objective): X = 14 µm/V, Y = 19 µm/V.'
    )

    add_heading(doc, '5.2  Fast and Slow Axes', level=2)
    doc.add_paragraph(
        'The raster scan has a fast axis (mirror sweeps back and forth) and a '
        'slow axis (mirror steps by one pixel after each line). '
        'By default the X axis is fast and Y is slow (raster_direction="x").'
    )

    add_heading(doc, '5.3  Padding Samples', level=2)
    doc.add_paragraph(
        'Each fast-axis line begins and ends with one extra sample equal to '
        'the first and last pixel voltage respectively. These padding samples '
        'give the FSM time to settle before the measurement window opens at '
        'the first real pixel. They must be discarded when mapping photon '
        'counts to pixel positions.'
    )
    add_code_block(doc,
        "# MATLAB original:\n"
        "# V_raster = [V(1), V(1:end), V(end)]\n"
        "\n"
        "# Python equivalent:\n"
        "V_fast_padded = np.concatenate([[V_fast[0]], V_fast, [V_fast[-1]]])\n"
    )

    add_heading(doc, '5.4  Output Array', level=2)
    doc.add_paragraph(
        'The function returns queued_data, a NumPy array of shape '
        '(N_samples, 2). Column 0 is the X voltage (ao0); column 1 is the '
        'Y voltage (ao1). This array is passed directly to the nidaqmx '
        'task.write() call.'
    )

    # -------------------------------------------------- Synchronisation
    add_heading(doc, '6. Synchronisation Strategy', level=1)
    doc.add_paragraph(
        'Unlike the Bassett Lab NI 6323 setup (which synchronises the DAQ '
        'analog output and photon counter via a shared hardware clock), this '
        'setup uses Python as the software coordinator:'
    )

    sync_points = [
        'Python knows the FSM position because it commanded it.',
        'Python triggers the Pulse Streamer at each pixel via ps.startNow().',
        'The Pulse Streamer embeds a marker pulse in every sequence; '
        'the Time Tagger timestamps this marker alongside photon arrivals.',
        'Post-processing segments the photon stream at marker boundaries '
        'to obtain per-pixel counts.',
    ]

    for point in sync_points:
        doc.add_paragraph(point, style='List Bullet')

    doc.add_paragraph(
        'This approach requires no shared hardware clock between myDAQ and '
        'Time Tagger and is well suited to step-and-measure scanning where '
        'the beam is stationary during each measurement.'
    )

    # -------------------------------------------------- Parameters
    add_heading(doc, '7. Key Scan Parameters', level=1)

    table = doc.add_table(rows=1, cols=3)
    table.style = 'Light Grid Accent 1'
    hdr = table.rows[0].cells
    for i, h in enumerate(['Parameter', 'Typical Value', 'Notes']):
        hdr[i].text = h
        hdr[i].paragraphs[0].runs[0].bold = True

    rows = [
        ('scan_center',   '[0, 0] µm',      'Center of scan relative to reference position'),
        ('scan_size',     '[5, 5] µm',       'Total scan area'),
        ('step_size',     '[0.1, 0.1] µm',  '100 nm pixel size'),
        ('scale',         '[14, 19] µm/V',  '60x air objective calibration'),
        ('clock_rate',    '400 Hz',          'Samples per second output by myDAQ'),
        ('raster_direction', 'x',            'Fast axis direction'),
        ('Pulse Streamer IP', '169.254.8.2', 'From lab network config'),
    ]

    for row_data in rows:
        row = table.add_row().cells
        for i, val in enumerate(row_data):
            row[i].text = val

    # -------------------------------------------------- File list
    add_heading(doc, '8. Files in This Folder', level=1)
    files = [
        ('scan_waveform.py',
         'Python waveform generator. Translated from FastSteeringMirror.m. '
         'Import generate_raster_waveform() in your scan script.'),
        ('confocal_scan_setup.docx',
         'This document.'),
    ]
    for fname, desc in files:
        p = doc.add_paragraph(style='List Bullet')
        p.add_run(fname).bold = True
        p.add_run(' — ' + desc)

    # ----------------------------------------------------------------- Save
    doc.save(OUTPUT_FILE)
    print(f"Document saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_document()
