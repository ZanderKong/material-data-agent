# Data Input Contract

## 1. Purpose and Scope

This document defines the recommended input format for the Material R&D Data Processing Agent. Following this contract improves automated data extraction accuracy and reduces manual review time. The system does not reject files outside the contract, but may generate quality flags requiring human review.

## 2. General Recommendations

- One file contains one data type (e.g., numeric measurements, spectral data, image, observation text).
- First row is a header with column names.
- CSV is recommended; Excel (`.xlsx`) is optional.
- UTF-8 encoding is recommended.
- File names should be descriptive and include the data type when practical.

### Required and Recommended Columns

- `sample_id` — required or strongly recommended for sample-level traceability.
- `batch_id` — recommended for batch-level grouping.
- Units belong in column names using standard abbreviations:
  - `thickness_um` (micrometers)
  - `resistance_ohm_sq` (sheet resistance)
  - `wavenumber_cm-1` (FTIR/Raman)
  - `wavelength_nm` (UV-Vis)
  - `absorbance`, `transmittance`, `reflectance`
  - `position` (measurement location on sample)

## 3. Numeric Data Format

```csv
sample_id,batch_id,position,thickness_um
A01,B01,center,32.1
A01,B01,edge,34.2
A02,B01,center,28.7
```

Rules:
- Numeric columns contain numeric values (integers or floating point).
- Missing values use blank cells or `NA`.
- Raw values are not manually rewritten before ingest.
- Do not mix units in the same column.

## 4. Spectral Data Format

```csv
wavenumber_cm-1,absorbance,sample_id,batch_id
4000,0.12,A01,B01
3999,0.13,A01,B01
3998,0.14,A01,B01
```

Rules:
- First column is the independent variable (e.g., wavenumber, wavelength).
- Subsequent columns contain measurement values.
- Column headers should name the measured quantity.
- Sample identifier columns allow multi-sample spectral files.

## 5. Image Data Format

Supported types: PNG, JPEG, GIF, WebP.

### Chart Screenshots
- Retain axes, axis labels, legend, units, and title in the image.
- Do not crop out scale information.
- Preferred resolution: readable text at screen size (approximately 800 px in the longest dimension or higher).

### Microscope / Surface Images
- Retain a scale bar where available.
- Do not apply filters that erase fine structure before ingest.

### Multi-panel Images
- Multi-panel figures require manual review.
- Single-panel images are processed more reliably.

## 6. Observation Text Format

UTF-8 plain text (`.txt`) or Markdown (`.md`). Separate factual observations from operator hypotheses.

### Example (Chinese)

```
[观察记录]
样品 A01 在退火后的表面出现均匀的蓝色氧化层。
膜厚测量结果为 32.1 um（中心）和 34.2 um（边缘）。
FTIR 谱图在 1700 cm-1 附近出现新的吸收峰。

[操作者推测]
蓝色氧化层可能为 TiO2。
1700 cm-1 吸收峰可能对应 C=O 伸缩振动，需进一步确认。
```

Rules:
- Label factual observations (`观察记录`) and hypotheses (`操作者推测`) explicitly.
- Include measurement values with units.
- Reference sample IDs used in other data files.
- Facts and interpretations are separated — the system will treat labeled hypotheses as interpretation candidates, not confirmed results.

## 7. Supported Tolerance

### The system may attempt

- Chinese and English column headers.
- Common unit forms (um/μm, ohm/sq, cm-1/cm⁻¹, nm).
- Blank, `NA`, `--`, and `N/A` as missing value markers.
- Mixed units across columns (when unit is in the column name).
- Low-confidence image extraction (chart axis labels, detected scale bars).
- Interpretation candidates from observation text.

### The system will not

- Invent missing sample IDs.
- Guess unknown units.
- Extract invisible or cropped-out axis labels.
- Read unreadable or absent scale bars.
- Assign labels to mixed unmarked samples.
- Auto-correct inconsistent measurements.

### Out-of-contract behavior

When input data falls outside the recommended contract, the system:
- Records the data structure as-is without modification.
- May produce `requires_review=True` quality flags.
- Does not fabricate a successful extraction for unreadable content.
- Marks low-confidence results and requests manual review.

## 8. Out-of-Contract Behavior

Data that cannot be confidently processed produces quality flags rather than silent failures or fabricated results. When the contract is not met, the system errs toward requiring human review rather than claiming automatic extraction success.

Typical out-of-contract indicators:
- Missing sample identifiers.
- Unlabeled columns with numeric data.
- Images without visible axes or scale bars.
- Observation text without clear fact/interpretation separation.
- Multiple data types mixed in a single file.

These files are still ingested and stored, but downstream processing may be limited until manual review confirms the data structure.
