"""PDK test cases"""
import logging
import os
from common import run_dir, get_filepath, generate_override_cmd_file
from extraction_utils.utils import lpe_extract, lpe_compare_rc, lpe_isotope, lpe_polo, \
    lpe_polo_compare
from waldo.pytest import fixture


def test_pdk_icv_complete_flow_with_starrc_spf_kwargs_with_csv_yaml(
        csv_input, waldo_rundir: fixture.RunDir):

    """Test case for running all test cases for defined series of test patterns for pdk1276 kit"""
    exclude_filter = []
    if csv_input.get('delete_star'):
        exclude_filter.append("**/star")
    if csv_input.get('delete_inputs'):
        exclude_filter.append("**/inputs")
    if csv_input.get('delete_run_details'):
        exclude_filter.append("**/run_details")
    if csv_input.get('delete_CCI'):
        exclude_filter.append("**/CCI")
    if csv_input.get('delete_svdb'):
        exclude_filter.append("**/SVDB")
    if csv_input.get('delete_milkyway'):
        exclude_filter.append("**/milkyway")

    fixture.Request.config.put('system.run_env.use_tmp_disk', True)
    fixture.Request.config.put('system.run_env.passing_profile', 'pass')
    fixture.Request.config.put('system.run_env.results.pass.include_filters', ["**/*"])
    fixture.Request.config.put('system.run_env.results.pass.exclude_filters', exclude_filter)
    fixture.Request.config.put('system.run_env.failing_profile', 'fail')
    fixture.Request.config.put('system.run_env.results.fail.include_filters', ["**/*"])
    fixture.Request.config.put('system.run_env.results.fail.exclude_filters', [])

    rundir = waldo_rundir.path
    complete_data_copy = csv_input.copy()
    combined_input_data = get_input_data(complete_data_copy)

    logging.info('combined input %s', combined_input_data)
    failed_test_patt = []

    # invoking lpe_extract

    extract_ret_code, spf_exist, sum_exist, combined_input_data = invoke_extract(combined_input_data, rundir)
    assert extract_ret_code == 0
    assert spf_exist is True
    assert sum_exist is True

    # invoking lpe_compareRC
    combined_input_data['Resextra'] = combined_input_data.get('Resextra').split() if \
        combined_input_data.get('Resextra') else combined_input_data.get('Resextra')
    if "-no_rc_compare" in combined_input_data.get('Resextra'):
        logging.info("lpe_compare_rc is skiping for %s cell", combined_input_data.get('cell_name'))
    else:
        lpe_compare_status, combined_input_data = invoke_lpe_compare(combined_input_data, rundir)
        if not lpe_compare_status:
            failed_test_patt.append("lpe_compare_rc")

    #  invoking lpe_isotope
    combined_input_data['Isotope_extra'] = combined_input_data.get('Isotope_extra').strip('-') if \
        combined_input_data.get('Isotope_extra') else None
    if not combined_input_data['Isotope_extra'] == 'no_run_expected':
        isotope_ret_code, combined_input_data = invoke_lpe_isotope(combined_input_data, rundir)
        if not isotope_ret_code:
            failed_test_patt.append("lpe_isotope")

        # invoking lpe_oa_isotope
        isotope_oa_ret_code, combined_input_data = invoke_lpe_isotope(combined_input_data, rundir)
        if not isotope_oa_ret_code:
            failed_test_patt.append("lpe_oa_isotope")

    if combined_input_data['testclass'] == "polo":
        # invoking lpe_polo
        polo_ret_code, combined_input_data = invoke_lpe_polo(combined_input_data, rundir)
        if polo_ret_code != 0:
            failed_test_patt.append("lpe_polo")
        else:
            polo_compare_ret, combined_input_data = invoke_lpe_polo_compare(combined_input_data,
                                                                            rundir)
            # invoking lpe_polo_compare
            if polo_compare_ret != 0:
                failed_test_patt.append("lpe_polo_compare")

        # invoking lpe_polo_oa
        polo_oa_ret_code, combined_input_data = invoke_lpe_polo_oa(combined_input_data, rundir)
        if polo_oa_ret_code != 0:
            failed_test_patt.append("lpe_polo_oa")
        else:
            # invoking lpe_polo_oa_compare
            polo_oa_compare_ret, combined_input_data = \
                invoke_lpe_polo_oa_compare(combined_input_data, rundir)
            if polo_oa_compare_ret != 0:
                failed_test_patt.append("lpe_polo_oa_compare")

        # invoking lpe_polo_smc_oa
        polo_smc_oa_ret_code, combined_input_data = invoke_lpe_polo_smc_oa(combined_input_data, rundir)
        if polo_smc_oa_ret_code != 0:
            failed_test_patt.append("lpe_polo_smc_oa")
        else:
            # invoking lpe_polo_smc_oa_compare
            polo_smc_oa_compare_ret, combined_input_data = \
                invoke_polo_smc_oa_compare(combined_input_data, rundir)
            if polo_smc_oa_compare_ret != 0:
                failed_test_patt.append("lpe_polo_smc_oa_compare")
    assert not failed_test_patt, (
        "TC is failed as following test patterns(s) are failed,"
        " Please refer to log files", failed_test_patt)


def get_input_data(combined_input_data):
    """ Method to get the combined input data from input csv and yaml file"""

    csv_keys = {'cellname': 'cell_name', 'libname': 'lib_name', 'temp':'temperature', 'nativestar':
    'native_star', 'gds': 'layout_filepath', 'oasis': 'layout_filepath', 'cdl':
    'schematic_filepath', 'Poloelement':'polo_element'}
    combined_input_data = combined_input_data.copy()
    for key in csv_keys.keys():
        if key in combined_input_data.keys():
            value = combined_input_data[key]
            del combined_input_data[key]
            combined_input_data[csv_keys[key]] = value
    combined_input_data['cds_lib_filepath'] = get_filepath('LPE.inc')
    combined_input_data['writeoa_output'] = bool(combined_input_data.get('writeoa'))
    combined_input_data['si_run_dir'] = ''
    combined_input_data['output_netlist_format'] = 'spf'
    combined_input_data['waiveoff_lvs_errors'] = combined_input_data.get('dirtylayout') if \
        combined_input_data.get('dirtylayout') else False
    combined_input_data['ndm_dbpath'] = ''
    combined_input_data['def_filepath'] = ''
    combined_input_data['annotated_gds_output'] = False
    xref = 'YES'
    if combined_input_data.get('layoutonly'):
        xref = 'NO'
    elif combined_input_data.get('dirtylayout'):
        if not combined_input_data.get('annotate'):
            xref = 'NO'
        else:
            xref = 'YES'
    elif combined_input_data.get('annotate'):
        xref = 'YES'
    user_override_values = {
        'devicexy': 'YES' if combined_input_data.get('devicexy') else 'NO',
        'xref_value': xref,
    }
    combined_input_data['rcx_lvs'] = bool(combined_input_data.get('nostdlvs'))
    reduction = not bool(combined_input_data.get('noredn'))
    if combined_input_data.get('extract_pg') and (combined_input_data.get('redn_pg') or
                                                  combined_input_data.get('noredn_pg')):
        reduction = bool(combined_input_data.get('redn_pg') or not combined_input_data.get(
            'noredn_pg'))
    combined_input_data['extract_optional_settings'] = {
        'smc': bool(combined_input_data.get('smc')),
        'reduction': reduction,
        'extract_pg': combined_input_data.get('extract_pg'),
        'overrides_cmd_files': [str(generate_override_cmd_file(user_override_values))],
        'reliability': bool(combined_input_data.get('reliability'))
    }
    combined_input_data['si_optional_settings'] = {'include_file': combined_input_data.get(
        'includecdl')}
    return combined_input_data


def invoke_extract(combined_input_data, rundir):
    if combined_input_data.get('flow') == "icv_starrcxt":
        combined_input_data['extract_tool'] = 'starrc'
        combined_input_data['lvs_tool_name'] = 'icv'
    if combined_input_data.get('flow') == "calibre_starrcxt":
        combined_input_data['extract_tool'] = 'starrc'
        combined_input_data['lvs_tool_name'] = 'calibre'
    if combined_input_data.get('flow') == "calibre_qrcxt":
        combined_input_data['extract_tool'] = 'qrc'
        combined_input_data['lvs_tool_name'] = 'calibre'
    extract_dir = combined_input_data['run_directory'] = run_dir(f'{rundir}/lpe_extract')
    combined_input_data['extract_dir'] = extract_dir
    extract_ret_code, spf_exist, sum_exist = lpe_extract.LpeExtract(**combined_input_data).run()
    return extract_ret_code, spf_exist, sum_exist, combined_input_data


def invoke_lpe_compare(combined_input_data, rundir):
    lpe_compare_status = ""
    smc = bool(combined_input_data.get('smc'))
    if not combined_input_data.get('Resextra') and not smc:
        if combined_input_data.get('Devextra') == "-compare_skew tttt" and \
                combined_input_data.get('skew') == "tttt":
            combined_input_data['test_spf_filepath'] = \
                os.path.join(str(combined_input_data.get('extract_dir')),
                             f'{combined_input_data.get("cell_name")}.spf')
            combined_input_data['reference_spf_filepath'] = \
                os.path.join(combined_input_data.get('reference_filepath'),
                             f'{combined_input_data.get("cell_name")}/'
                             f'{combined_input_data.get("flow")}/'
                             f'{combined_input_data.get("skew")}'
                             f'/{combined_input_data.get("temperature")}/'
                             f'{combined_input_data.get("cell_name")}.spf')
        else:
            combined_input_data['test_spf_filepath'] = os.path.join(
                str(combined_input_data.get('extract_dir')), f'{combined_input_data.get("cell_name")}.spf')
            combined_input_data['reference_spf_filepath'] = \
                os.path.join(combined_input_data.get('reference_filepath'),
                             f'{combined_input_data.get("cell_name")}/'
                             f'{combined_input_data.get("flow")}/'
                             f'{combined_input_data.get("skew")}'
                             f'/{combined_input_data.get("temperature")}/'
                             f'{combined_input_data.get("cell_name")}.spf')
    elif smc and "-udc_compare" in combined_input_data.get('Resextra'):
        corner_skew_temp = combined_input_data.get('Resextra')[1].split(',')
        corner = corner_skew_temp[0]
        smc_skew = corner_skew_temp[1]
        smc_temp = corner_skew_temp[2]
        combined_input_data['test_spf_filepath'] = os.path.join(
            str(combined_input_data.get('extract_dir')),
            f'{combined_input_data.get("cell_name")}.spf.{smc_skew}_{smc_temp}')
        combined_input_data['reference_spf_filepath'] = \
            os.path.join(combined_input_data.get('reference_filepath'),
                         f'{combined_input_data.get("cell_name")}/smc-icv_starrcxt/separate/'
                         f'{combined_input_data.get("cell_name")}.spf.{corner}')
    combined_input_data['run_directory'] = run_dir(f'{rundir}/lpe_compare')
    rptgen_returncode, reggen_returncode, tcap, ccap, p2p = \
        lpe_compare_rc.LpeCompareRC(**combined_input_data).compare_rc()
    if rptgen_returncode != 0 or reggen_returncode != 0 or tcap != 'pass' or \
            ccap != 'pass' or p2p != 'pass':
        lpe_compare_status = False
    return lpe_compare_status, combined_input_data


def invoke_lpe_isotope(combined_input_data, rundir):

    #  invoking lpe_isotope
    combined_input_data['run_directory'] = run_dir(f'{rundir}/lpe_isotope')
    combined_input_data['spf_vs_spf'] = True
    combined_input_data['oa_vs_spf'] = False
    isotope_ret_code = lpe_isotope.Isotope(**combined_input_data).run()
    return isotope_ret_code, combined_input_data


def invoke_lpe_oa_isotope(combined_input_data, rundir):
    # invoking lpe_oa_isotope
    combined_input_data['run_directory'] = run_dir(f'{rundir}/lpe_oa_isotope')
    combined_input_data['cds_lib_filepath'] = get_filepath('LPE.inc')
    combined_input_data['spf_vs_spf'] = False
    combined_input_data['oa_vs_spf'] = True
    isotope_oa_ret_code = lpe_isotope.Isotope(**combined_input_data).run()
    return isotope_oa_ret_code, combined_input_data


def invoke_lpe_polo(combined_input_data, rundir):
    combined_input_data['pct_error'] = int(combined_input_data.get('Poloextra').split(" ")[1])
    combined_input_data['run_directory'] = run_dir(f'{rundir}/lpe_polo')
    polo_obj = lpe_polo.LpePolo(**combined_input_data)
    polo_ret_code, _ = polo_obj.run()
    return polo_ret_code, combined_input_data


def invoke_lpe_polo_compare(combined_input_data, rundir):
    # invoking lpe_polo_compare
    combined_input_data ['run_directory'] = run_dir(f'{rundir}/lpe_polo_compare')
    combined_input_data['new_polo_file'] = f'{rundir}/lpe_polo/' \
                                           f'{combined_input_data.get("cell_name")}.out'
    combined_input_data['old_polo_file'] = \
        os.path.join(combined_input_data.get('previous_polo_filepath'),
                     f'{combined_input_data.get("cell_name")}/'
                     f'polo/'
                     f'{combined_input_data.get("skew")}/'
                     f'{combined_input_data.get("cell_name")}.out')

    polo_compare_obj = lpe_polo_compare.LpePoloCompare(**combined_input_data)
    polo_compare_ret = polo_compare_obj.run_compare()
    return polo_compare_ret, combined_input_data


def invoke_lpe_polo_oa(combined_input_data, rundir):
    # invoking lpe_polo_oa
    combined_input_data['run_directory'] = run_dir(f'{rundir}/lpe_polo_oa')
    combined_input_data['extraction_view'] = "oa"
    polo_oa_obj = lpe_polo.LpePolo(**combined_input_data)
    polo_oa_ret_code, _ = polo_oa_obj.run()
    return polo_oa_ret_code, combined_input_data


def invoke_lpe_polo_oa_compare(combined_input_data, rundir):

    # invoking lpe_polo_oa_compare
    combined_input_data['run_directory'] = run_dir(f'{rundir}/lpe_polo_oa_compare')
    combined_input_data['new_polo_file'] = f'{rundir}/lpe_polo_oa/' \
                                           f'{combined_input_data.get("cell_name")}.out'
    combined_input_data['old_polo_file'] = \
                    os.path.join(combined_input_data.get('previous_polo_oa_filepath'),
                     f'{combined_input_data.get("cell_name")}/'
                     f'polo/{combined_input_data.get("skew")}/'
                     f'{combined_input_data.get("cell_name")}.out')
    polo_oa_compare_obj = lpe_polo_compare.LpePoloCompare(**combined_input_data)
    polo_oa_compare_ret = polo_oa_compare_obj.run_compare()
    return polo_oa_compare_ret, combined_input_data


def invoke_lpe_polo_smc_oa(combined_input_data, rundir):
    combined_input_data['run_directory'] = run_dir(f'{rundir}/lpe_polo_smc_oa')
    combined_input_data['extraction_view'] = "smc-oa"
    polo_smc_oa_obj = lpe_polo.LpePolo(**combined_input_data)
    polo_smc_oa_ret_code, _ = polo_smc_oa_obj.run()
    return polo_smc_oa_ret_code, combined_input_data


def invoke_polo_smc_oa_compare(combined_input_data, rundir):
    combined_input_data['run_directory'] = run_dir(f'{rundir}/lpe_polo_smc_oa_compare')
    combined_input_data['new_polo_file'] = f'{rundir}/lpe_polo_smc_oa/' \
                                      f'{combined_input_data.get("cell_name")}.out'
    combined_input_data['old_polo_file'] = \
        os.path.join(combined_input_data.get('previous_polo_smc_oa_filepath'),
                     f'{combined_input_data.get("cell_name")}/'
                     f'polo/typ_nom/'
                     f'{combined_input_data.get("cell_name")}.out')
    polo_smc_oa_compare_obj = lpe_polo_compare.LpePoloCompare(**combined_input_data)
    polo_smc_oa_compare_ret = polo_smc_oa_compare_obj.run_compare()
    return polo_smc_oa_compare_ret, combined_input_data
