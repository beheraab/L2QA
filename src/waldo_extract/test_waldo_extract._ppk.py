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


WEXTRACT_DATA_DIR = str(Path(__file__).parent / 'data')

profiles_spec = f'''
icv_native {{
    config_files = [{WEXTRACT_DATA_DIR}/profiles/profile2/icv_star_native_ppk.conf]
    id = icv_native
    nb_resource = 32G1C
    runs = [run1]
}},
'''


profiles = wconfig.from_str(profiles_spec)
TESTCASES_DIR = f"{WEXTRACT_DATA_DIR}/testcases"
DEF_NB_RESOURCE = '32G1C'

def gen_params():

    layout_testcases = glob.glob(f'{TESTCASES_DIR}/*.stm')
    for layout in layout_testcases:
        cell = Path(layout).stem
        netlist = f"{TESTCASES_DIR}/{cell}.cdl"
        if Path(netlist).exists():
            profile_name = 'icv_native'
            data = wconfig.merge(wconfig.empty(), profiles.get(profile_name))
            data.put('settings.condition.temperature', ['110'])
            data.put('settings.condition.skew', ['tttt'])
            data.put('settings.input.cell', cell)
            data.put('settings.input.layout', layout)
            data.put('settings.input.netlist', netlist)
            #data.put('settings.eda.smc', False)
            #data.put('settings.eda.smcpair', False')
            data.put('xfail', False)

            # data.put('settings.misc.norun', True)  # norun
            nb_resource = data.get('nb_resource', DEF_NB_RESOURCE)
            marks = [pytest.mark.netbatch(resource=nb_resource)]
            if data['xfail']:
                marks.append(pytest.mark.xfail(reason='Expected to fail'))

            yield pytest.param(data, id=f"{data['id']}_{cell}", marks=marks)


@pytest.mark.parametrize('params', gen_params())
def test_extensive_flow(monkeypatch, waldo_rundir: RunDir, params):

    config_files = params['config_files']
    runs = params['runs']
    id = params['id']
    xfail = params['xfail']

    overrides = wconfig.merge(wconfig.empty(), params['settings'])

    monkeypatch.chdir(waldo_rundir.path)

    # Merge all config files with default config
    configs = wconfig.merge(wconfig.empty(), wconfig.from_file(waldo_extract.DEFAULT_CFG),
                            *[Path(config_file) for config_file in config_files])

    os.environ['WEXTRACT_DATA_DIR'] = WEXTRACT_DATA_DIR
    ConfigParser.resolve_substitutions(configs, accept_unresolved=True)  # resolve WALDO_UAT_TESTCASE_DIR

    runs_settings = waldo_extract_utils.compute_settings(configs, runs, overrides)

    run0_settings = runs_settings[runs[0]]
    cell_name = run0_settings.get('input.cell')
    extension = run0_settings.get('output.netlist_format', 'spf')

    #merge per setting configs with the global config coming from pconf
    per_setting = wconfig.merge(wconfig.empty(), Request.config, configs)

    initialize_cadroot(per_setting)
    waldo_extract_utils.run_extraction(runs_settings, per_setting)

    subdir = configs.get('extract_common_settings.output.run_dir')
    extraction_run_dir = configs.get('extract_common_settings.output.extraction_run_dir')

    spf_files = list(Path(waldo_rundir.path, subdir, extraction_run_dir).glob(f'{cell_name}*.*{extension}*'))
    oa_files = list(Path(waldo_rundir.path).glob(f'**/{cell_name}/*/layout.oa'))

    print('Search location:', Path(waldo_rundir.path, subdir, extraction_run_dir))
    print('SPF files:', spf_files)
    print('OA files:', oa_files)

    if xfail:
        pytest.xfail('expected fail')
    else:
        if extension == 'oa':
            assert len(oa_files) > 0, 'OA file does not exist'
        else:
            assert len(spf_files) > 0, 'SPF file does not exist'
