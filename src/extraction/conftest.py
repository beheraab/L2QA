"""Common methods used in pytests"""
import glob
import os
import re
from pathlib import Path
import logging
import pandas as pd
import yaml
from waldo.model import Kit


def yaml_data() -> dict:
    """This is fixture, used to return the input data from inputs from yaml file.

        Returns
        -------
        yaml_inputs_data: dict
            Dictionary of input parameters from yaml file.

        Raises
        ------
        FileNotFoundError
            Given input file is not available.

    """
    yaml_inputs = {}
    try:
        file_name = str(Path(__file__).parent / 'testcase_inputs.yaml')
        with open(file_name, 'r', encoding='utf8') as yaml_file:
            parser = yaml.load(yaml_file, Loader=yaml.FullLoader)
            if parser:
                yaml_inputs = parser
                logging.info("Input parameters: %s", yaml_inputs)
            else:
                logging.exception('Input file %s is empty', file_name)
            if not os.path.exists(yaml_inputs.get('tests_csv_filepath')):
                raise FileNotFoundError

            return yaml_inputs
    except FileNotFoundError as error:
        logging.exception("FileNotFoundError at yaml_data method: %s ", error)
        raise error


yaml_inputs_data = yaml_data()

def get_skew_from_kit():
    """This method to get skew list for a specified kit"""
    skews = []
    kit_name = yaml_inputs_data.get('kit_name')
    tech_opt = yaml_inputs_data.get('tech_opt')
    kit = Kit.get(kit_name, tech_opt)
    models_dir_string = kit.root
    models_dir_string += "/extraction/starrc/techfiles/"
    oa_library = os.path.join(models_dir_string, '**', '*.nxtgrd')
    model_files = glob.glob(oa_library, recursive=True)
    for each_model_file in model_files:
        skew = each_model_file.split('/')[-1].split('.')[0]
        skews.append(skew)
    skews_list = list(set(skews))
    skews_listto_str = ','.join([str(skew_element) for skew_element in skews_list])
    return skews_listto_str

ALL_SKEWS_FROM_KIT = get_skew_from_kit()


def getresult(scriptextra_params):
    """This method used to convert scriptextra string to dict and a pandas series from those key
    value pairs"""
    key = []
    value = []
    for paramindex, _ in enumerate(scriptextra_params):
        if re.match(r'^-\w*', scriptextra_params[paramindex]):
            key.append(scriptextra_params[paramindex].split('-')[1])
            if paramindex != len(scriptextra_params) - 1 and \
                    re.match(r'^[^-]+', scriptextra_params[paramindex + 1]):
                value.append(scriptextra_params[paramindex + 1])
            else:
                value.append(True)
    row_series = pd.Series(value)
    row_series.index = key
    return row_series


def prep_csv_data():
    """This method used to return the csv data prepared for creation of testcases.
            Returns
            -------
            csv_input_list: list
                List of dictionary of parameters from input csv file having testcases for kit

            Raises
            ------
            ValueError
                Raised if given condition is not met.

        """
    csv_file_name = yaml_inputs_data.get('tests_csv_filepath')
    data_frame = pd.read_csv(csv_file_name)
    for idx, row in data_frame.iterrows():
        row_dict = getresult(row.get('Scriptextra').split())
        for key, value in row_dict.to_dict().items():
            data_frame.loc[idx, key] = value
            row[key] = value
        if not row.get('nosmc') and not row.get('skew'):
            data_frame.loc[idx, 'smc'] = True
            row['smc'] = True
            data_frame.loc[idx, 'skew'] = ''
            data_frame.loc[idx, 'temp'] = ''
        if row.get('nosmc') and not row.get('skew'):
            data_frame.loc[idx, 'skew'] = ALL_SKEWS_FROM_KIT
        if row.get('skew'):
            data_frame.loc[idx,'skew'] = row.get('skew')
        if row.get('nosmt') and len(row.get('temp').split(',')) > 1:
            raise ValueError(f"Temperature value cannot be more than one with nosmt option for row"
                             f" number {idx + 1}")
        if not row.get('smc'):
            data_frame['skew'] = data_frame['skew'].str.split(',')
    data_frame.drop(columns=['Scriptextra'], inplace=True)
    data_frame = data_frame[data_frame['skew'].apply(lambda x: not isinstance(x, list) or len(x) > 0)]
    data_frame['temp'] = data_frame['temp'].str.split(',')
    data_frame['flow'] = data_frame['flow'].str.split(',')
    data_frame = data_frame.explode('skew', ignore_index=True)
    data_frame = data_frame.explode('temp', ignore_index=True)
    data_frame = data_frame.explode('flow', ignore_index=True)
    dataframe_obj = data_frame.fillna("")
    csv_input_list = list(dataframe_obj.T.to_dict().values())
    [csv_input.update(yaml_inputs_data) for csv_input in csv_input_list]
    return csv_input_list

csv_input_data = prep_csv_data()


def pytest_generate_tests(metafunc):
    """Method to genrate pytests from parametrization"""
    test_data = {}
    keys = []
    for item in csv_input_data:
        global key
        if item.get('smc'):
            key = item.get('cellname') + '_smc_' + item.get('flow')
        else:
            key = item.get('cellname') + '_' + item.get('skew') + '_' + item.get('temp') + '_' + \
                  item.get('flow')
        keys.append(key)
        test_data[key] = item
    metafunc.parametrize('csv_input', csv_input_data, ids=keys)
