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
    with open('/nfs/site/disks/x5e2d_workarea_beheraab_002/waldo/extraction_WW36.3/src/waldo_extract/modified_kit_POR.csv' , 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        # file_reader = csv.DictReader(file)
        for row in csv_reader:
            profile_name = row['profile']
            data = wconfig.merge(wconfig.empty(), profiles.get(profile_name))
            data.put('settings.input.cell',row['cell_name']) ## rev
            data.put('settings.input.layout',row["layout"])
            data.put('settings.input.library',row["lib_name"])
            # test1 = data.get('settings.input.library')
            data.put('settings.input.netlist',row['netlist'])
            data.put('settings.condition.temperature', row['temperature'].split())
            data.put('settings.condition.skew', row['skew'].split())
            #data.put('settings.eda.smc', row['smc'].strip() == 'True')
            #data.put('settings.eda.smcpair', row['smcpair'].strip() == 'True')
            #data.put('xfail', row['xfail'].strip() == 'True')
            data.put('xfail', False)

#    layout_testcases = glob.glob(f'{TESTCASES_DIR}/testcases/tc3t_stinv_pars_e.oas')
#    for layout in layout_testcases:
#        cell = Path(layout).stem
#       netlist = f"{TESTCASES_DIR}/testcases/{cell}.cdl"
#      if Path(netlist).exists():
#
#            profile_name = 'icv_native'
#            data = wconfig.merge(wconfig.empty(), profiles.get(profile_name))
#            data.put('settings.condition.temperature', ['25'])
#            data.put('settings.condition.skew', ['tttt'])
#            data.put('settings.input.cell', cell)
#            data.put('settings.input.layout', layout)
#            data.put('settings.input.netlist', netlist)
#            #data.put('settings.eda.smc', False)
#            #data.put('settings.eda.smcpair', False')
#            data.put('xfail', False)#

            # data.put('settings.misc.norun', True)  # norun
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
    #print("anbhg")
   # print(f"{params['settings']}")
   # print("before:", waldo_rundir.path)
    monkeypatch.chdir(waldo_rundir.path)  #change the current directory to waldo_rundir.path
    #print("after:", waldo_rundir.path)
    # Merge all config files with default config
    configs = wconfig.merge(wconfig.empty(), wconfig.from_file(waldo_extract.DEFAULT_CFG),
                            *[Path(config_file) for config_file in config_files])
    # waldo_extract.DEFAULT_CFG = /nfs/site/disks/x5e2d_gwa_bibartan_01/WALDO/.virtualenvs/WW35.2/lib/python3.9/site-packages/wtool/extract/config/defaults.conf
    #print("before resolution,", configs, "\n")
    os.environ['WEXTRACT_DATA_DIR'] = WEXTRACT_DATA_DIR
    ConfigParser.resolve_substitutions(configs, accept_unresolved=True)  # resolve WALDO_UAT_TESTCASE_DIR , whyyyyy??????
    #print("after resolution,", configs, "\n")
    runs_settings = waldo_extract_utils.compute_settings(configs, runs, overrides)
    #print(runs_settings)
    run0_settings = runs_settings[runs[0]]
    #print(run0_settings)
    #cell_name = run0_settings.get('input.cell')
    #extension = run0_settings.get('output.netlist_format')
    #print(extension)
    run1_settings = runs_settings[runs[1]]
    cell_name = run1_settings.get('input.cell')
    extension = run1_settings.get('output.netlist_format')
    #print(extension)
    # create new library. Library is created per test due to contention issues that may raise with
    # multiple tests writing to one nfs location.
    if extension == 'oa':
        cds_lib = str(Path(waldo_rundir.path, 'cds.lib'))
        kit = Kit.get(run0_settings.get('pdk.pdk_name'), run0_settings.get('pdk.tech_opt'))
        waldo_extract_utils.create_new_library(kit=kit,
                                               output_cds_lib=cds_lib,
                                               run_dir=waldo_rundir.path,
                                               lib_name='oa_lib',
                                               cds_lib_include=cds_lib_include,
                                               lib_path=Path(waldo_rundir.path, 'oa_lib'))
        #print(waldo_rundir)

        run0_settings.put("output.oa_view.cds_lib", cds_lib)


    #merge per setting configs with the global config coming from pconf
    per_setting = wconfig.merge(wconfig.empty(), Request.config, configs)
    print("runs settings:", runs_settings, '\n')
    print("per_setting:", per_setting)
    initialize_cadroot(per_setting)
    waldo_extract_utils.run_extraction(runs_settings, per_setting)


    subdir = configs.get('extract_common_settings.output.run_dir')
    extraction_run_dir = configs.get('extract_common_settings.output.extraction_run_dir')

    spf_files = list(Path(waldo_rundir.path, subdir, extraction_run_dir).glob(f'{cell_name}*.spf'))
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

#new push to branch
