# IndelQuant

IndelQuant is a desktop GUI workflow for amplicon-based genome editing analysis. It wraps common preprocessing, demultiplexing, read-merging, CRISPResso2 execution, result parsing, summary export, and visualization steps into a single Windows-friendly interface.

Repository: [rexhancx/IndelQuant](https://github.com/rexhancx/IndelQuant)

The application is designed for small to medium targeted amplicon sequencing projects where users need to split barcode-indexed samples, generate merged reads, run CRISPResso2, and inspect editing outcomes without manually assembling long command lines.

## Features

- Graphical workflow for FASTQ input, barcode demultiplexing, read merging, and CRISPResso2 analysis.
- AdapterRemoval v3 integration for barcode-based demultiplexing and paired-end read merging.
- CRISPResso2 integration for amplicon editing quantification.
- Optional fastp preprocessing/QC support.
- Real-time logging of external tool output.
- Automatic monitoring of CRISPResso2 result files.
- Automatic parsing of `CRISPResso_quantification_of_editing_frequency.txt`.
- Sample table with reads aligned, modified percentage, and unmodified percentage.
- Summary CSV export.
- Built-in visualization of editing efficiency across samples.
- Windows path handling and drag-and-drop input support.

## Workflow

1. Select paired FASTQ files and a barcode table.
2. Run AdapterRemoval v3 to demultiplex barcode-indexed reads.
3. Merge paired-end reads into per-sample FASTQ files.
4. Configure amplicon and guide RNA sequences.
5. Run CRISPResso2 for selected samples.
6. Monitor progress in the GUI log panel.
7. Review per-sample editing results and plots.
8. Export summary tables for downstream analysis or publication.

## Requirements

IndelQuant is developed and tested primarily on Windows.

Required Python packages:

```text
customtkinter
matplotlib
numpy
pandas
openpyxl
windnd
```

External command-line tools:

- AdapterRemoval v3 (`adapterremoval3`)
- CRISPResso2 (`CRISPResso`)
- fastp, if using fastp preprocessing

## Installation

Create and activate a conda environment:

```bash
conda create -n crispranalysis python=3.9 -y
conda activate crispranalysis
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install external tools:

```bash
conda install -c bioconda adapterremoval fastp -y
pip install CRISPResso2
```

Before using CRISPResso2, make sure your use complies with the CRISPResso2 license terms. See the license notes below.

## Usage

Start the GUI:

```bash
python main.py
```

On Windows, you can also run:

```bat
run.bat
```

In the GUI:

1. Open the AdapterRemoval page and select `R1`, `R2`, and the barcode table.
2. Set the output prefix, usually `demux`.
3. Open the CRISPResso2 page and enter the amplicon sequence and guide RNA sequence.
4. Go to the run workspace and run AdapterRemoval, CRISPResso2, or the full workflow.
5. Inspect the result table and visualization panel.

## Barcode Table Format

Use a whitespace- or tab-delimited barcode table:

```text
SampleA    ACGTACGT
SampleB    TGCATGCA
```

For paired barcode designs, provide sample name plus both barcode sequences according to AdapterRemoval v3 requirements.

## Outputs

Typical output files include:

- `demux.<sample>.merged.fastq`
- `CRISPResso_on_<sample>/`
- `CRISPResso_quantification_of_editing_frequency.txt`
- `crispr_summary.csv`
- CRISPResso2 HTML reports and plots

## Citation

If you use IndelQuant in a publication, please cite this article and software repository.

Duan, Y.; Xu, K.; Zhou, H.; He, C.; Ding, J.; Qin, C.; Zhang, Y.; Han, C.; Meng, H. IndelQuant: A Workflow for Cost-Efficient Amplicon Sequencing Analysis of Genome-Edited Chickens. Int. J. Mol. Sci. 2026, 27, 9054. https://doi.org/10.3390/ijms27209054

Please cite CRISPResso2 according to the official CRISPResso2 documentation and publication information.

Please cite AdapterRemoval v3 as recommended by the AdapterRemoval project. 

If fastp is used, cite the fastp publication recommended by the fastp project.

## License And Third-Party Tools

IndelQuant is released under the Apache License 2.0.

IndelQuant is a GUI wrapper and workflow coordinator. AdapterRemoval, CRISPResso2, and fastp are third-party tools and are not redistributed as part of this source repository. Users are responsible for installing and using these tools under their respective license terms.

- CRISPResso2 is distributed under its own EULA for academic/non-commercial research use and should not be redistributed with this repository unless you have permission from the CRISPResso2 rights holder.
- AdapterRemoval v3 is GPL-3.0 licensed. If you redistribute AdapterRemoval itself or bundle it into a release, you must comply with GPL-3.0.
- fastp is MIT licensed.

See `THIRD_PARTY_NOTICES.md` for additional third-party license notes.

## Disclaimer

IndelQuant is intended for research use. It is not a clinical diagnostic tool and should not be used for clinical decision-making.
