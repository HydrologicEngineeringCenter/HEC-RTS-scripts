# HEC-RTS Scripts

Field-tested **Jython** scripts for the US Army Corps of Engineers **Real-Time Simulation (HEC-RTS)** / **CAVI** environment (and, because HEC-RTS shares the CWMS directory layout, for CWMS watersheds too).

The collection covers three recurring needs in an operational forecasting watershed:

1. **Backup data acquisition** — pull USGS, HADS, and NWS RFC (NWPS) time series into a local HEC-DSS file on demand or on a schedule, independent of the operational shefloader/acquisition pipeline.
2. **Forecast post-processing** — vertical datum conversions (NGVD29 / local datum ↔ NAVD88) and clearing HEC-ResSim overrides in the active forecast.
3. **Modeling support** — a shared starting template for "Modeling tab" scripts and a GUI helper for managing an HEC-HMS calibration library.

Everything here is intended to be **copied into your own watershed and edited**, not installed. Treat it as a worked set of examples for RTS scripting patterns more than as a supported product.

---

## Requirements

| Item | Detail |
| --- | --- |
| Application | HEC-RTS 3.x (or CWMS CAVI), which embeds the Jython interpreter |
| Language | **Jython 2.7**, *not* Python 3 — these files use `print` statements, `except Exception, e:` and Java class imports |
| Data store | HEC-DSS file(s) reachable from the workstation |
| Network | `hads.ncep.noaa.gov`, `api.water.noaa.gov` (NWPS), and the USGS water services, as needed by the acquisition scripts |
| Context | Most scripts require the **Modeling tab to be selected and a forecast open** (they call `chktab()` / `chkfcst()` and read the active forecast's DSS file) |

Scripts use the standard RTS entry points:

* `com.rma.client.Browser` → current project, selected tab, active forecast, `fcst.getOutDssPath()`
* `hec2.rts.script.RTS` → `RTS.getWatershed()`, `getProjectDirectory()`, `RTS.getCurrentModule()`
* `hec.heclib.dss.HecDss`, `hec.io.TimeSeriesContainer`, `hec.heclib.util.HecTime`, `hec.script.MessageBox`

---

## Installation

1. Download or clone this repository.

   ```
   git clone https://github.com/HydrologicEngineeringCenter/HEC-RTS-scripts.git
   ```

2. Copy the `.py` files you need into your watershed. Conventions used by these scripts:

   | Directory | Contents |
   | --- | --- |
   | `<cwms_home>\scripts\` or `<cwms_home>\watershed\<watershed>\scripts\` | scripts referenced by the Script Editor or by a Scripting program in the Program Order |
   | `<cwms_home>\watershed\<watershed>\shared\source\` | the `extract_*.config` files, the `.<watershed>.hads` / `.<watershed>.rfc` / `.<watershed>.usgs` site lists, and shared helper modules |
   | `<cwms_home>\watershed\<watershed>\shared\` | `verticalDatumOffsets.txt` (used by `29_to_88.py`) |
   | `<cwms_home>\database\...` | output DSS files, e.g. `USGS_Data\`, `HADS_Data\`, `RFC_Data\` |

   `Extract_USGS.py` adds `...\shared\source` to `sys.path`, so keeping the config files and any helper modules in that folder is what makes the config ↔ extractor pairing work automatically.

3. Register a script in RTS the usual way:
   * **Ad hoc / GUI:** Setup or Modeling module → *Script → Editor…* → New → paste or point at the file → *Save/Run*.
   * **In the forecast sequence:** Setup → Watershed tree → right-click **Scripting** → **New** → point the *Jython Script* field at the file → assign a model key → add it to a Program Order. For that use case the script must define
     `computeAlternative(currentAlternative, computeOptions)` and return `True` on success — see the commented block in `Modeling_Tab_Script_Template.py`.
   * **Unattended:** *Script → Schedule Script Job…* for periodic acquisition.

---

## Repository layout

| File | Purpose |
| --- | --- |
| `Extract_USGS.py` | Retrieves USGS gage data into DSS using the RTS/CWMS USGS plugin and a `.usgs` control file |
| `Extract_USGS_Config.py` | GUI to create/edit `extract_usgs.config` (`.usgs` file path + output DSS path) |
| `Extract_HADS.py` | Downloads HADS `DecodedData` (pipe-delimited) for a list of GOES IDs and stores SHEF elements in DSS |
| `Extract_HADS_Config.py` | GUI to create/edit `extract_hads.config` (`.hads` list + output DSS path) |
| `Extract_HADS_Site_Selector.py` | GUI: browse/filter the published USGS HADS site lists by state, stage a subset, auto-build DSS pathnames, export the `.hads` list |
| `Extract_RFC.py` | Downloads NWS RFC/NWPS stage-flow JSON per gauge, splits observed vs. forecast, stores both in DSS |
| `Extract_RFC_Config.py` | GUI to create/edit `extract_rfc.config` (`.rfc` list + output DSS path) |
| `Extract_RFC_Site_Selector.py` | GUI: browse/filter NWPS gauges by ID/name/state/WFO/RFC, stage a subset, auto-build DSS pathnames, export the site list |
| `29_to_88.py` | Shifts elevation records between NGVD29 / local datum and NAVD88 in the active forecast DSS file |
| `Clear_ResSim_Overrides.py` | Clears one or all HEC-ResSim override sets in the active forecast's override DSS file |
| `HMS_Calibration_Library.py` | GUI for managing an HEC-HMS calibration library (local folder + optional remote/shared folder) against the active forecast |
| `Modeling_Tab_Script_Template.py` | Boilerplate for any script that needs the open forecast: DSS handle, time window, error dialogs |
| `.vscode/settings.json` | IntelliSense paths for the HEC Jython VS Code extension (edit the hard-coded user path) |

---

## Backup time series acquisition (USGS / HADS / RFC)

All three families follow the same three-step pattern, and each script ends with a scrollable, wrapped log popup summarizing (or explaining) the run.

```
1. Extract_<X>_Site_Selector.py   ->  build the site list  (optional; hand-edit it instead)
2. Extract_<X>_Config.py          ->  write <X>_file + dss_file into extract_<x>.config
3. Extract_<X>.py                 ->  fetch and store to DSS (prompts for lookback)
```

Each `extract_*.config` is a plain `key=value` text file (blank line / `#` comment handling included):

```ini
# HADS extract paths config
version=1
hads_file=C:\cwms_home\watershed\MyWatershed\shared\source\MyWatershed.hads
dss_file=C:\cwms_home\database\HADS_Data\MyWatershed_TimeSeries.dss
```

Defaults offered by the config builders (all derived from the current watershed name):

| Source | Default site list | Default output DSS |
| --- | --- | --- |
| USGS | `<watershed>\shared\source\<name>.usgs` | `<cwms_home>\database\USGS_Data\<name>_TimeSeries.dss` |
| HADS | `<watershed>\shared\source\<name>.hads` | `<cwms_home>\database\HADS_Data\<name>_TimeSeries.dss` |
| RFC | `<watershed>\shared\source\<name>.rfc` | `<cwms_home>\database\RFC_Data\<name>_TimeSeries.dss` |

### USGS

`Extract_USGS.py` drives `hec.plugins.usgs.UsgsControlFrame` against the resolved DSS file, so it uses the same station-control syntax as the built-in USGS acquisition and inherits its units/rating behaviour.

* Time window: taken from the current RTS module when available; otherwise you are prompted for days back (capped at `MAX_LOOKBACK_DAYS = 800`).
* Must run **inside CAVI** — outside of it the script exits with "This script must be run inside CAVI."
* Creates the output folder and DSS file if they do not exist.
* Missing, empty, or unconfigured control file → beep + error dialog naming the path it looked for.

### HADS

`Extract_HADS.py` reads `https://hads.ncep.noaa.gov/nexhads2/servlet/DecodedData` in pipe (`of=1`) format, one request carrying all configured `nesdis_ids`.

* Prompts for **1–7 days** of lookback (default 2) — the DecodedData service only serves a short window, which is why this is a *backup* feed.
* Converts `DD MM SS.S` lat/lon strings to decimal degrees (longitude assumed west).
* SHEF element → DSS C-part/units mapping is an easily extended dictionary at the top of the file:

  | SHEF | Parameter | Units |
  | --- | --- | --- |
  | `HG` | Stage | ft |
  | `HG2` | Stage-bkup | ft |
  | `QR` | Flow | cfs |
  | `PC` | Precip | in |
  | `VB` | Battery | v |
  | `SD` | Snow Depth | in |
  | `TA` | Air Temp | F |
  | `TW` | Water Temp | F |
  | `WS` | Wind Speed | fps |
  | `WT` | Turbidity | ppm |

* Network failures are retried (3 attempts, 5 s backoff) with the attempts written to the log.

Site list (`<name>.hads`) — blank-line-separated blocks, `GOES_ID` and `DSS_PATH` required:

```
NWS_ID=LOUZ1
USGS_ID=02177150
GOES_ID=CRCP0
HSA=MD
LAT=38 23 30.2
LON=090 38 16.1
NAME=LOWER IQUOITZA CREEK NEAR LOAME
DSS_PATH=/MyWatershed/LOUZ1////HADS/
```

### RFC (NWPS)

`Extract_RFC.py` reads `https://api.water.noaa.gov/nwps/v1/gauges/<GAUGE_ID>/stageflow`, separates the `observed` and `forecast` blocks, and writes them as sibling records off the configured base pathname:

| Record | C-part | E-part / F-part |
| --- | --- | --- |
| Observed stage / flow | `Stage` / `Flow` | `IR-Day`, F-part suffixed ` -Obs` (e.g. `RFC-Obs`) |
| Forecast stage / flow | `Stage` / `Flow` | `IR-Day`, F-part suffixed ` -Forecast` |

Units come from the API payload (`primaryUnits` = stage, `secondaryUnits` = flow) with `ft` / `cfs` fallbacks; record type is `INST-VAL`. Set `DEBUG_JSON_SNIPPET = True` to echo partial JSON into the log when a gauge misbehaves.

Site list (`<name>.rfc`) — `GAUGE_ID` and `DSS_PATH` required:

```
GAUGE_ID=LOUZ1
NAME=LOAME CREEK AT LOAME
STATE=MD
WFO=BOX
RFC=AORC
LAT=38.391722
LON=-90.637806
DSS_PATH=/MyWatershed/LOUZ1////RFC/
```

### Site selector GUIs

Both selectors are `JDialog`-based and share the same interaction model:

* **Load/Reload** pulls the published catalog (`https://hads.ncep.noaa.gov/USGS/<ST>_USGS-HADS_SITES.txt` for HADS; the NWPS gauge list for RFC) into a filterable table (state, ID, HSA/WFO/RFC, name contains).
* A **DSS naming** row lets you pick the A-part (watershed, optional), how the B-part is derived (NWS ID, USGS ID, name, gauge ID, WFO/RFC variants…), and the F-part (source tag, e.g. `HADS` or `RFC`). Pathname parts are sanitized (slashes → `-`, illegal characters stripped) and produced as `/A/B////F/`.
* Selected rows are added to an editable **staging list** with the DSS pathname snapshotted at add time; you can add blank rows for manual/ad-hoc sites and re-open an existing list to append to it (de-duplicated).

---

## Forecast post-processing

### `29_to_88.py` — vertical datum conversion

Converts elevation records in the **active forecast's** output DSS file using offsets in `...\watershed\<name>\shared\verticalDatumOffsets.txt`:

```
# NGVD29 -> NAVD88 and local -> NAVD88 offsets, keyed on the DSS B-part
#29-88#FLOW.LOAME_CREEK       +1.24
#29-88#POOL.TROUTVILLE        +1.24
#LOCAL-88#STAGE.LOAME_GAGE    -0.37
```

Each line is `#<29|LOCAL>-88#<B-part><separator><signed offset>`; B-part matching is case-insensitive and tolerates complex B-parts.

Direction is chosen by the **scripting program name** (`progname = arg2`), so this single file is registered twice:

| Program name | Behaviour |
| --- | --- |
| `29_to_88` | Reads records whose C-part starts with `ELEV(29)` or `ELEV(LOCAL)`, adds the offset, and writes them back with the datum suffix stripped (plain `ELEV` = NAVD88) |
| `88_to_29` | Reads plain `ELEV` records, subtracts the offset, and writes copies with `(29)` or `(LOCAL)` appended to the C-part |

`Constants.UNDEFINED` values are skipped, and the run reports `Shifted N values in M records - K location(s) skipped`, listing any B-parts that have records in the forecast but no offset defined.

### `Clear_ResSim_Overrides.py`

Finds the active HEC-ResSim alternative (prompts if the forecast run has more than one), opens the matching override file at `<forecast dir>\rss\<F-part>`, and lists the override sets found in its condensed catalog. You then clear **one set** or **all sets**; clearing writes DSS undefined (`-3.4028e38`) into the values. The closing dialog reminds you to recompute ResSim from CAVI before computing downstream models in OSI.

---

## Modeling support

### `HMS_Calibration_Library.py`

GUI for moving HEC-HMS calibration files between three places:

* the **local library** — `...\watershed\<name>\hms\forecast\calibration_library` (created on first run if absent),
* an optional **remote/shared library** — a directory path stored in `Remote_Calibration_Library_Directory.txt` inside the local library (defaults to `Not Defined`),
* the **active forecast**, whose `hms\forecast\<Alternative>.forecast` file is located from the active HMS alternative with spaces and punctuation replaced by underscores.

### `Modeling_Tab_Script_Template.py`

Copy this to start any new Modeling-tab script. It handles the parts every one of these scripts repeats:

* `chktab()` / `chkfcst()` guards, `output()` / `error()` console helpers
* opening `fcst.getOutDssPath()` and setting the DSS time window to the forecast's *start ; forecast ; end* triple
* paired `################## Stection-Start/End ##################` markers to bracket your own code
* `try/except` for both Python and Java exceptions, dumping a full traceback into a `MessageBox`
* `cwmsFile.done()` in `finally`
* a commented `computeAlternative()` stub for when the script joins a Program Order

---

