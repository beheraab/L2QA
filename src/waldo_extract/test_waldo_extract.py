"""Test for waldo-extract flow"""
import os
import csv
from pathlib import Path
import pytest
from pyhocon import ConfigParser

from waldo.pytest import RunDir, Request
from waldo.util import config as wconfig
from wtool.extract.cli import waldo_extract


WEXTRACT_DATA_DIR = str(Path(__file__).parent / 'data')

profiles_spec = f'''
calibre_ccp {{
    config_files = [{WEXTRACT_DATA_DIR}/profiles/profile1/calibre_star_ccp.conf]
    id = calibre_ccp
    nb_resource = 32G1C
    runs = [run1]
}}
icv_ccp {{
    config_files = [{WEXTRACT_DATA_DIR}/profiles/profile1/icv_star_ccp.conf]
    id = icv_ccp
    nb_resource = 32G1C
    runs = [run1]
}}
icv_qtf {{
    config_files = [{WEXTRACT_DATA_DIR}/profiles/profile1/icv_star_native_qtf.conf]
    id = icv_qtf
    nb_resource = 32G1C
    runs = [run1]
}}
icv_native {{
    config_files = [{WEXTRACT_DATA_DIR}/profiles/profile1/icv_star_native.conf]
    id = icv_native
    nb_resource = 32G1C
    runs = [run1]
}}
'''


profiles = wconfig.from_str(profiles_spec)
TESTCASES_CSV = 'testcases.csv'
DEF_NB_RESOURCE = '32G1C'

def gen_params():

    def filter(csv_file):
        for row in csv_file:
            if row.split('#')[0].strip():  # not a comment
                yield row

    with open(Path(__file__).parent / TESTCASES_CSV, 'r') as file:
        csvfile = filter(file)
        file_reader = csv.DictReader(csvfile)
        # file_reader = csv.DictReader(file)
        for row in file_reader:
            profile_name = row['profile']
            data = wconfig.merge(wconfig.empty(), profiles.get(profile_name))
            data.put('settings.condition.temperature', row['temperature'].split())
            data.put('settings.condition.skew', row['skew'].split())
            data.put('settings.eda.smc', row['smc'].strip() == 'True')
            data.put('settings.eda.smcpair', row['smcpair'].strip() == 'True')
            data.put('xfail', row['xfail'].strip() == 'True')

            # data.put('settings.misc.norun', True)  # norun
            nb_resource = data.get('nb_resource', DEF_NB_RESOURCE)
            marks = [pytest.mark.netbatch(resource=nb_resource)]
            if data['xfail']:
                marks.append(pytest.mark.xfail(reason='Expected to fail'))

            yield pytest.param(data, id=f"{data['id']}_{int(row['id']):03}", marks=marks)


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

    runs_settings = waldo_extract.compute_settings(configs, runs, overrides)

    run0_settings = runs_settings[runs[0]]
    cell_name = run0_settings.get('input.cell')

    #merge per setting configs with the global config coming from pconf
    per_setting = wconfig.merge(wconfig.empty(), Request.config, configs)

    waldo_extract.initialize_cadroot(per_setting)
    waldo_extract.run_extraction(runs_settings, per_setting)


    subdir = configs.get('extract_common_settings.output.run_dir')
    starrc_dir = configs.get('extract_common_settings.output.extraction_run_dir')

    spf_files = list(Path(waldo_rundir.path, subdir, starrc_dir).glob(f'{cell_name}.*spf*'))

    print('Search location:', Path(waldo_rundir.path, subdir, starrc_dir))
    print('SPF files:', spf_files)

    if xfail and len(spf_files) == 0:
        pytest.xfail('expected fail')

    assert len(spf_files) > 0, 'SPF file does not exist'
