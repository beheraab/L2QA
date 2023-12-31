"""Test for waldo-extract flow"""
from importlib.resources import contents
import os
import csv
from pathlib import Path
import glob
from textwrap import wrap
from xml.dom.expatbuilder import CDATA_SECTION_NODE
import pytest
import pytest_check
from pyhocon import ConfigParser
from waldo.pytest.fixture import Request
from waldo.pytest import RunDir, initialize_cadroot
from waldo.util import config as wconfig
from wtool.extract.cli import waldo_extract
from wtool.extract import waldo_extract_utils
from waldo.model import Kit, ToolExec
from waldo.tool.virtuoso.oasisout import OasisOut
from waldo.tool.virtuoso import si, VirtuosoToolSetupError, CdsLib

WEXTRACT_DATA_DIR = str(Path(__file__).parent / 'data')
WEXTRACT_DIR = str(Path(__file__).parent)
matching_paths = []
#root_folder = "/nfs/site/disks/icf_fdk_tcmgr003/1278/"
cds_libs = {}
cds_content = []

profiles_spec = f'''
icv_native {{
    config_files = [{WEXTRACT_DATA_DIR}/profiles/profile2/icv_star_native_ppk.conf]
    id = icv_native
    nb_resource = 32G1C
    runs = [run1,run2]
}}
calibre_native {{
    config_files = [{WEXTRACT_DATA_DIR}/profiles/profile2/calibre_star_native_ppk.conf]
    id = calibre_native
    nb_resource = 32G1C
    runs = [run1,run2]
}}
calibre_qrc {{
    config_files = [{WEXTRACT_DATA_DIR}/profiles/profile2/calibre_qrc_native_ppk.conf]
    id = calibre_qrc
    nb_resource = 32G1C
    runs = [run1,run2]
}}
'''
profiles = wconfig.from_str(profiles_spec)
TESTCASES_DIR = f"{WEXTRACT_DATA_DIR}/"
DEF_NB_RESOURCE = '32G1C'
CDS_LIB_DIR = f"{WEXTRACT_DATA_DIR}/profiles/profile3/cds.lib"

oas_cdl_generated_dict = dict()


def generate_oas_cdl_params():

    with open(f'{WEXTRACT_DIR}/kit_POR.csv', 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            # Convert values to integers since CSV data is read as strings
            profile_name = row['profile']
            data = wconfig.merge(wconfig.empty(), profiles.get(profile_name))
            data.put('settings.input.cell', row['cell_name'])   # rev
            data.put('settings.input.category', row['category'])
            #data.put('settings.input.opt', row['tech_opt'])
            data.put('settings.input.cdslib', CDS_LIB_DIR)
            data.put('settings.input.library', row['lib_name'])
            data.put('settings.input.profile', row['profile'])
            data.put('settings.condition.temperature', row['temperature'].split())
            data.put('settings.condition.skew', row['skew'].split())
            if (len(row['skew'].split()) > 1):
                data.put('settings.eda.starrc.smc', 'True')
                data.put('settings.eda.starrc.smcpair', 'True')
            else:
                print("There is only one temperature skew, smc: False, smcpair: False")
            data.put('xfail', False)

            nb_resource = data.get('nb_resource', DEF_NB_RESOURCE)
            marks = [pytest.mark.netbatch(resource=nb_resource)]
            if data['xfail']:
                marks.append(pytest.mark.xfail(reason='Expected to fail'))

            yield pytest.param(data, id=f"{data['id']}_{data['settings.input.cell']}", marks=marks)

# Use the @pytest.mark.parametrize decorator with the generator function
@pytest.mark.parametrize("data", generate_oas_cdl_params())
def test_extraction_flow(data, waldo_rundir: RunDir, waldo_kit: Kit, monkeypatch):

    os.environ['WALDO_RUN_DIR'] = str(Path(waldo_rundir.path))

    # waldo_kit.__init__(kit_name=Request.config.get('kit_name'),
    #                     tech_opt=Request.config.get('tech_opt'),
    #                     iter=Request.config.get('iteration'))
    os.environ['DOTNAME'] = waldo_kit.dotname

    ds_root_folder = Request.config.get('designsync_root_folder')
    #exit(1)
    print("Kit: ", waldo_kit, "\n")
    include_file_path = glob.glob(os.path.abspath(os.path.join(waldo_kit.get_component_path("libraries_custom_cdl"), '..', '..', '..')) + "/*.pcell")[0]
    # Iterate over all items in the root_folder
    for item in os.listdir(ds_root_folder):
        item_path = os.path.join(ds_root_folder, item)

        # Check if the item is a directory and starts with "qa78"
        if os.path.isdir(item_path) and item.startswith("qa78"):
            # Inside the "qa78" folder, look for a subfolder named "Trunk::Latest"
            trunk_latest_folder_path = os.path.join(item_path, "Trunk::Latest")

            # Check if the "Trunk::Latest" folder exists
            if os.path.exists(trunk_latest_folder_path) and os.path.isdir(trunk_latest_folder_path):
                # Inside the "Trunk::Latest" folder, look for a subfolder with the same name as the parent folder
                subfolder_path = os.path.join(trunk_latest_folder_path, item)

                # Check if the subfolder with the same name exists
                if os.path.exists(subfolder_path) and os.path.isdir(subfolder_path):
                    matching_paths.append(subfolder_path)
                    cds_libs[item] = subfolder_path

    data.put("libraries", cds_libs)
    define_list = [f"DEFINE {key} {value}" for key, value in data['libraries'].items()]
    if 'user_cds_path' in Request.config:
        print("User cds custom exists \n")
        user_define_list = [f"DEFINE {key} {value}" for key, value in Request.config.get('user_cds_path').items()]

    #print("Config dictionary: ", user_define_list, "\n")
    with open(CDS_LIB_DIR, 'w') as file:
        file.write("INCLUDE " + include_file_path + '\n')
        for row in define_list:
            file.write(row + '\n')

        # Check if a variable named 'user_define_list' exists in the local scope
        if 'user_define_list' in locals():
            for row in user_define_list:
                file.write(row + '\n')

    #print("Libraries: ", define_list, "\n")
    try:
        oasisout = OasisOut(kit=waldo_kit,
                            run_dir=waldo_rundir.path,
                            lib_name=data['settings.input.library'],
                            cell_name=data['settings.input.cell'],
                            cds_lib=CDS_LIB_DIR)
    except RuntimeError as err:
        assert not str(err)

    oasisout.set_capture(to_str=True, to_stdout=False, to_logfile='oas_log.log')
    exitcode_oas, stdout_oas, stderr_oas = oasisout.run()

    try:
        summary = oasisout.summary()
        errors = summary.errors
        if errors:
            with pytest_check.check:
                for err in errors:
                    assert not err
            return
    except (RuntimeError, FileNotFoundError):
        pass # to be reconsidered
    assert exitcode_oas == 0, stderr_oas or stdout_oas  # to be reconsidered

    # Combine intel78custom.cdl and intel78prim.cdl files
    with open(glob.glob(waldo_kit.get_component_path("libraries_custom_cdl") + "/*.cdl")[0], 'r') as include_file:
        content1 = include_file.read()

    with open(glob.glob(waldo_kit.get_component_path("libraries_prim_cdl") + "/*.cdl")[0], 'r') as include_file:
        content2 = include_file.read()

    with open(glob.glob(waldo_kit.get_component_path("libraries_sram_cdl") + "/*.cdl")[0], 'r') as include_file:
        content3 = include_file.read()

    with open(glob.glob(waldo_kit.get_component_path("libraries_tic_cdl") + "/*.cdl")[0], 'r') as include_file:
        content4 = include_file.read()

    with open(glob.glob(waldo_kit.get_component_path("libraries_halo_cdl") + "/*.cdl")[0], 'r') as include_file:
        content5 = include_file.read()

    #print("Path1: ", glob.glob(waldo_kit.get_component_path("libraries_custom_cdl") + "/*.cdl")[0], "\n") #intel78tic.cdl
    # print("Path2: ", glob.glob(waldo_kit.get_component_path("libraries_prim_cdl") + "/*.cdl")[0], "\n")
    # print("Path3: ", glob.glob(waldo_kit.get_component_path("libraries_sram_cdl") + "/*.cdl")[0], "\n")
    # print("Path4: ", glob.glob(waldo_kit.get_component_path("libraries_tic_cdl") + "/*.cdl")[0], "\n")

    # print("Path6: ", glob.glob(waldo_kit.get_component_path("libraries_halo_cdl") + "/*.cdl")[0], "\n")

    #exit(1)
    #$INTEL_PDK/etc/kit.index.yaml

    combined_content = content1 + content2 + content3 + content4 + content5

    with open(str(Path(waldo_rundir.path, "combined_include_file.cdl")), 'w') as combined_include_file:
        combined_include_file.write(combined_content)

    try:
        cdlout = si.Si(kit=waldo_kit,
                        lib_name=data['settings.input.library'],
                        cell_name=data['settings.input.cell'],
                        run_dir=waldo_rundir.path,
                        cds_lib=CDS_LIB_DIR,
                        include_file=str(Path(waldo_rundir.path, "combined_include_file.cdl")))
    except RuntimeError as err:
        assert not str(err)

    cdlout.set_capture(to_str=False, to_stdout=False, to_logfile='cdl_log.log')
    exitcode_cdl, stdout_cdl, stderr_cdl = cdlout.run()
    assert exitcode_cdl == 0, stderr_cdl or stdout_cdl

    data.put('settings.input.layout', str(Path(waldo_rundir.path, f"{data['settings.input.cell']}.oas")))
    data.put('settings.input.netlist', str(Path(waldo_rundir.path, f"{data['settings.input.cell']}.cdl")))
    oas_cdl_generated_dict[data['settings.input.cell']] = data
    print("Result path: ", data,  "\n")
    print("Si netlist dir: ", Request.config.get, "\n")
    #####################OAS CDL GENERATION FINISHED############################
    config_files = data['config_files']
    runs = data['runs']
    id = data['id']
    xfail = data['xfail']
    cds_lib_include = data.get('cds_lib_include', None)

    # save pdk settings from waldo_kit (created with settings from default.conf)
    data.put('settings.pdk.pdk_name', waldo_kit.name)
    data.put('settings.pdk.tech_opt', waldo_kit.techopt)
    data.put('settings.pdk.iteration', waldo_kit.iter)

    overrides = wconfig.merge(wconfig.empty(), data['settings'])
    #print("Overrides: ", data['settings.pdk.kit'], "\n")

    monkeypatch.chdir(waldo_rundir.path)  #change the current directory to waldo_rundir.path

    # Merge all config files with default config
    configs = wconfig.merge(wconfig.empty(), wconfig.from_file(waldo_extract.DEFAULT_CFG), *[Path(config_file) for config_file in config_files])
    # waldo_extract.DEFAULT_CFG = /nfs/site/disks/x5e2d_gwa_bibartan_01/WALDO/.virtualenvs/WW35.2/lib/python3.9/site-packages/wtool/extract/config/defaults.conf

    os.environ['WEXTRACT_DATA_DIR'] = WEXTRACT_DATA_DIR
    os.environ['CATEGORY'] = data['settings.input.category']
    ConfigParser.resolve_substitutions(configs, accept_unresolved=True)  # resolve WALDO_UAT_TESTCASE_DIR , whyyyyy??????
    runs_settings = waldo_extract_utils.compute_settings(configs, runs, overrides)
    run0_settings = runs_settings[runs[0]]
    #cell_name = run0_settings.get('input.cell')
    #extension = run0_settings.get('output.netlist_format')
    run1_settings = runs_settings[runs[1]] #runs2
    cell_name = run1_settings.get('input.cell')
    extension = run1_settings.get('output.netlist_format')
    # create new library. Library is created per test due to contention issues that may raise with
    # multiple tests writing to one nfs location.
    name_oa = "oa_lib"
    if extension == 'oa':
        cds_lib = str(Path(waldo_rundir.path, 'cds.lib'))
        # kit = Kit.get(kit_name=run0_settings.get('pdk.pdk_name'),
        #               tech_opt=run0_settings.get('pdk.tech_opt'),
        #               iter=run0_settings.get('pdk.iteration'))
        waldo_extract_utils.create_new_library(kit=waldo_kit,
                                                output_cds_lib=cds_lib,
                                                run_dir=waldo_rundir.path,
                                                lib_name=name_oa,
                                                cds_lib_include=cds_lib_include,
                                                lib_path=Path(waldo_rundir.path, name_oa))

        run0_settings.put("output.oa_view.cds_lib", cds_lib)

    #merge per setting configs with the global config coming from pconf
    per_setting = wconfig.merge(wconfig.empty(), Request.config, configs)
    initialize_cadroot(per_setting)
    waldo_extract_utils.run_extraction(runs_settings, per_setting)

    subdir = configs.get('extract_common_settings.output.run_dir')
    extraction_run_dir = configs.get('extract_common_settings.output.extraction_run_dir')
    rcx_lvs_dir = configs.get('extract_common_settings.output.lvs_run_dir')

    ############START:Failure Checks################################

    # icv.log
    if data['id'] == 'icv_native':
        icv_log_file = str(Path(waldo_rundir.path, subdir, rcx_lvs_dir, "icv.log" ))
        try:
            with open(icv_log_file, "r") as file:
                file_content = file.read()
                # Assert that the target string is not present in the file content
                assert "IC Validator is done." in file_content, f"IC Validation failed for {data['settings.input.cell']}. Check {icv_log_file} for errors"
        except FileNotFoundError:
            pytest.xfail(f"File '{icv_log_file}' not found")

        #<cell_name>.RESULTS
        layout_results_file = str(Path(waldo_rundir.path, subdir, rcx_lvs_dir, f"{data['settings.input.cell']}.RESULTS" ))
        try:
            with open(layout_results_file, "r") as file:
                file_content = file.read()
                # Assert that the target string is not present in the file content
                assert "DRC and Extraction Results: CLEAN" in file_content, f"DRC and Extraction failed for {data['settings.input.cell']}. Check {layout_results_file} for errors"
                assert "LVS Compare Results: PASS" in file_content, f"LVS Compare failed for {data['settings.input.cell']}"
        except FileNotFoundError:
            pytest.xfail(f"File '{layout_results_file}' not found")

        #<cell_name>.TOP_LAYOUT_ERRORS
        layout_top_errors_file = str(Path(waldo_rundir.path, subdir, rcx_lvs_dir, f"{data['settings.input.cell']}.TOP_LAYOUT_ERRORS" ))
        try:
            with open(layout_top_errors_file, "r") as file:
                file_content = file.read()
                # Assert that the target string is not present in the file content
                assert "TOP LAYOUT ERRORS RESULTS: CLEAN" in file_content, f"Top layout errors present in {data['settings.input.cell']}. Check {layout_top_errors_file} for errors"
        except FileNotFoundError:
            pytest.xfail(f"File '{layout_top_errors_file}' not found")
    elif data['id'] == 'calibre_native':
        print("--------Code to be written---------- \n")
    elif data['id'] == 'calibre_qrc':
        print("--------Code to be written---------- \n")
    elif data['id'] == 'pegasus_qrc':
        print("--------Code to be written---------- \n")

    ############END:Failure Checks################################

    source_path = f"{waldo_rundir.path}/*/"
    print("Source path: ", source_path, "\n")
    # kitname = configs.get('extract_common_settings.pdk.pdk_name')
    # opt = configs.get('extract_common_settings.pdk.tech_opt')
    kitname = waldo_kit.name
    opt = waldo_kit.techopt
    destination_path = f"/p/fdk/f1278/debug_iind/central_runs/{kitname}_{opt}/test/{data['settings.input.library']}/extraction_pcell_cdl_native/{data['settings.input.cell']}/"
    print(f"Destination_path: {destination_path} \n")
    # Create the chain of folders
    os.makedirs(destination_path, exist_ok=True)
    command = f'cp -Rvf {source_path} {destination_path}'

    #os.system(command)
    #print("copy command executed \n")

    spf_files = list(Path(waldo_rundir.path, subdir, extraction_run_dir).glob(f'{cell_name}*.spf'))
    oa_files = list(Path(waldo_rundir.path).glob(f'**/{cell_name}/*/layout.oa'))

    if xfail:
        pytest.xfail('expected fail')
    else:
        if extension == 'oa':
            assert len(oa_files) > 0, 'OA file does not exist'
        else:
            assert len(spf_files) > 0, 'SPF file does not exist'