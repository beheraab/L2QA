"""Test for waldo-extract flow"""
import os
import csv
from pathlib import Path
import glob
import pytest
from pyhocon import ConfigParser
from waldo.pytest.fixture import Request
from waldo.pytest import RunDir, initialize_cadroot
from waldo.util import config as wconfig
from wtool.extract.cli import waldo_extract
from wtool.extract import waldo_extract_utils
from waldo.model import Kit,ToolExec
from waldo.tool.virtuoso.oasisout import OasisOut
from waldo.tool.virtuoso import si, VirtuosoToolSetupError, CdsLib

WEXTRACT_DATA_DIR = str(Path(__file__).parent / 'data')

profiles_spec = f'''
icv_native {{
    config_files = [{WEXTRACT_DATA_DIR}/profiles/profile2/icv_star_native_ppk.conf]
    id = icv_native
    nb_resource = 32G1C
    runs = [run1,run2]
}},
'''
profiles = wconfig.from_str(profiles_spec)
TESTCASES_DIR = f"{WEXTRACT_DATA_DIR}/"
DEF_NB_RESOURCE = '32G1C'

def gen_params():
    with open('/nfs/site/disks/x5e2d_workarea_beheraab_002/waldo/extraction_WW38.4/src/waldo_extract/modified_kit_POR.csv' , 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)

        for row in csv_reader:
            profile_name = row['profile']
            data = wconfig.merge(wconfig.empty(), profiles.get(profile_name))
            data.put('settings.input.cell',row['cell_name']) ## rev
            data.put('settings.input.layout',row["layout"])
            data.put('settings.input.library',row["lib_name"])
            data.put('settings.input.netlist',row['netlist'])
            data.put('settings.condition.temperature', row['temperature'].split())
            data.put('settings.condition.skew', row['skew'].split())
            if(len(row['skew'].split())>1):
                #data.put('settings.eda.smc', row['smc'].strip() == 'True')
                data.put('settings.eda.starrc.smc', 'True')
                #data.put('settings.eda.smcpair', row['smcpair'].strip() == 'True')
                data.put('settings.eda.starrc.smcpair', 'True')
            else:
                print("There is only one temperature skew, smc: False, smcpair: False")
            data.put('xfail', False)

            nb_resource = data.get('nb_resource', DEF_NB_RESOURCE)
            marks = [pytest.mark.netbatch(resource=nb_resource)]
            if data['xfail']:
                marks.append(pytest.mark.xfail(reason='Expected to fail'))

            yield pytest.param(data, id=f"{data['id']}_{data['settings.input.cell']}", marks=marks)

@pytest.mark.parametrize('params', gen_params())

def test_extensive_flow(monkeypatch, waldo_rundir: RunDir, params):

    config_files = params['config_files']
    runs = params['runs']
    id = params['id']
    xfail = params['xfail']
    cds_lib_include = params.get('cds_lib_include', None)
    overrides = wconfig.merge(wconfig.empty(), params['settings'])
    monkeypatch.chdir(waldo_rundir.path)  #change the current directory to waldo_rundir.path

    # Merge all config files with default config
    configs = wconfig.merge(wconfig.empty(), wconfig.from_file(waldo_extract.DEFAULT_CFG),
                            *[Path(config_file) for config_file in config_files])
    # waldo_extract.DEFAULT_CFG = /nfs/site/disks/x5e2d_gwa_bibartan_01/WALDO/.virtualenvs/WW35.2/lib/python3.9/site-packages/wtool/extract/config/defaults.conf

    os.environ['WEXTRACT_DATA_DIR'] = WEXTRACT_DATA_DIR
    os.environ['LIB_NAME'] = params['settings.input.library']
    ConfigParser.resolve_substitutions(configs, accept_unresolved=True)  # resolve WALDO_UAT_TESTCASE_DIR , whyyyyy??????
    runs_settings = waldo_extract_utils.compute_settings(configs, runs, overrides)
    run0_settings = runs_settings[runs[0]]
    #cell_name = run0_settings.get('input.cell')
    #extension = run0_settings.get('output.netlist_format')
    run1_settings = runs_settings[runs[1]]
    cell_name = run1_settings.get('input.cell')
    extension = run1_settings.get('output.netlist_format')
    # create new library. Library is created per test due to contention issues that may raise with
    # multiple tests writing to one nfs location.
    name_oa = "oa_lib"
    if extension == 'oa':
        cds_lib = str(Path(waldo_rundir.path, 'cds.lib'))
        kit = Kit.get(run0_settings.get('pdk.pdk_name'), run0_settings.get('pdk.tech_opt'))
        waldo_extract_utils.create_new_library(kit=kit,
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

    source_path = f"{waldo_rundir.path}/{subdir}"
    print("Source path: ", source_path, "\n")
    kitname = configs.get('extract_common_settings.pdk.pdk_name')
    opt = configs.get('extract_common_settings.pdk.tech_opt')
    destination_path = f"/p/fdk/f1278/debug_iind/central_runs/{kitname}_{opt}/test/{params['settings.input.library']}/extraction_pcell_cdl_native/{params['settings.input.cell']}/"
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