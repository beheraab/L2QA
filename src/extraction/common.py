import os
from pathlib import Path
import logging
from waldo.util import template


def generate_override_cmd_file(user_values: dict):
    user_cmd_file = str((Path(__file__).parent / 'data' / 'overrides.cmd'))
    settings = {
        'src_file': str(Path(__file__).parent / 'data' / 'user_cmd.j2'),
        'dst_file': user_cmd_file,
        'values': user_values
    }
    _, undefined = template.generate(**settings)
    if len(undefined) != 0:
        raise RuntimeError(f'Undefined variables while setting up options: {str(undefined)}')
    return user_cmd_file


def get_filepath(file_name) -> str:
    """ Function to file path from input cds file string"""
    file_path = Path(__file__).parent / 'data' / file_name
    if not file_path.exists():
        logging.exception('Given file %s is missing', file_name)
        raise FileNotFoundError
    return str(file_path)


def run_dir(run_directory):
    """This method to add run_name to current rundir"""
    try:
        if Path(run_directory).exists():
            logging.info("Work area exists: %s", run_directory)
        else:
            os.makedirs(run_directory)
            logging.info("Created work area %s ", run_directory)
        return run_directory
    except Exception as error:
        logging.exception("Issue occured while creating run directory: %s", error)
        raise error
