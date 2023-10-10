"""Test for waldo-extract flow"""
import os
import csv
from pathlib import Path
import glob
import pytest
import pytest_check
from pyhocon import ConfigParser
from waldo.pytest.fixture import Request
from waldo.pytest import RunDir, initialize_cadroot
from waldo.util import config as wconfig
from wtool.extract.cli import waldo_extract
from wtool.extract import waldo_extract_utils
from waldo.model import Kit,ToolExec
from waldo.tool.virtuoso.oasisout import OasisOut
from waldo.tool.virtuoso import si, VirtuosoToolSetupError, CdsLib

# WEXTRACT_DATA_DIR = str(Path(__file__).parent / 'data')
# TESTCASES_DIR = f"{WEXTRACT_DATA_DIR}/testcases"
#tmp_dir = '/nfs/site/disks/x5e2d_workarea_beheraab_002/waldo/extraction_WW36.3/src/waldo_extract/data/testcases/'
oas_files = []
cells_list = []

# Define a fixture to perform cleanup after all test cases
@pytest.fixture(scope="session")
def cleanup_after_all_tests(request):
    # This code will be executed before all tests
    yield
    # This code will be executed after all tests are completed
    print("Performing cleanup after all tests...")
    # You can add your cleanup logic here

# Define a generator function that yields input data and expected results
def generate_test_cases(): #read each entry of csv

    with open('/nfs/site/disks/x5e2d_workarea_beheraab_002/waldo/extraction_WW38.4/src/waldo_extract/kit_POR.csv', 'r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            # Convert values to integers since CSV data is read as strings
            test_data = dict()
            kit_name = row['pdk_name']
            opt_number = row['tech_opt']
            test_data['kit'] = Kit.get(kit_name, opt_number)
            test_data['lib_name'] = row['lib_name']
            test_data['cell_name'] = row['cell_name']
            test_data['cds_lib_path'] = row['cds_lib']
            yield pytest.param(test_data, id=f"{kit_name}_{opt_number}_{test_data['lib_name']}_{test_data['cell_name']}")

# Parametrize the test function with the generator function
@pytest.mark.parametrize("test_data", generate_test_cases())

def test_func(test_data, waldo_rundir: RunDir):

    try:
        oasisout = OasisOut(kit=test_data['kit'],
                            run_dir=waldo_rundir.path,
                            lib_name=test_data['lib_name'],
                            cell_name=test_data['cell_name'],
                            cds_lib=test_data['cds_lib_path'])
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
    assert exitcode_oas == 0, stderr_oas or stdout_oas # to be reconsidered

    try:
        cdlout = si.Si(kit=test_data['kit'],
                        lib_name=test_data['lib_name'],
                        cell_name=test_data['cell_name'],
                        run_dir=waldo_rundir.path,
                        cds_lib=test_data['cds_lib_path'])
    except RuntimeError as err:
        assert not str(err)

    cdlout.set_capture(to_str=False, to_stdout=False, to_logfile='cdl_log.log')
    exitcode_cdl, stdout_cdl, stderr_cdl = cdlout.run()
    assert exitcode_cdl == 0, stderr_cdl or stdout_cdl

    cells = dict()
    # suggestion: it can be a dictionary of dictionary
#     Dictionary of dictionaries -> e,g
    # {
    #     'cell a': {
    #             'layout' : '/path/to/layout',
    #             'netlist': 'path/to/netlist'
    #                 }
    # }

    cells['cell_name'] = test_data['cell_name']
    cells['layout'] = glob.glob(((f'{waldo_rundir.path}/*.oas')))[0]
    cells['netlist'] = glob.glob(((f'{waldo_rundir.path}/*.cdl')))[0]
    cells_list.append(cells)



# The cleanup fixture will ensure this function runs after all tests
def test_cleanup(cleanup_after_all_tests):
    # Your cleanup logic here
    input_csv_file = "/nfs/site/disks/x5e2d_workarea_beheraab_002/waldo/extraction_WW38.4/src/waldo_extract/kit_POR.csv"
    with open(input_csv_file, 'r') as csv_input:
        reader = csv.DictReader(csv_input)
        csv_data = [row for row in reader]

    # clean this up. Suggestion: read the csv as a dictionary and add the paths in dict() and then dump it back in csv
    name_to_path_dict = {entry["cell_name"]: entry["layout"] for entry in cells_list}
    name_to_netlist_dict = {entry["cell_name"]: entry["netlist"] for entry in cells_list}

    for record in csv_data:
        name = record["cell_name"]
        path = name_to_path_dict.get(name, "")
        path_netlist = name_to_netlist_dict.get(name, "")
        record["layout"] = path
        record["netlist"] = path_netlist


    output_csv_file = "/nfs/site/disks/x5e2d_workarea_beheraab_002/waldo/extraction_WW38.4/src/waldo_extract/modified_kit_POR.csv"
    with open(output_csv_file, 'w', newline='') as csv_output:
        fieldnames = ['pdk_name','tech_opt','profile','lib_name','cell_name','cds_lib','temperature','skew','layout','netlist']  # Use the existing fieldnames
        writer = csv.DictWriter(csv_output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)

    csv_output.close()
    pass
