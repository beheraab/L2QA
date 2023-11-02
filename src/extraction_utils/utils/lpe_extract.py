"""This file performs the extraction flow"""
import logging
import sys
import fileinput
from pathlib import Path
from waldo.tool.virtuoso import si
from waldo.tool.virtuoso import oasisout
from .helpers import Helpers
from wtool.extract import utils


class LpeExtract:
    """ Class used to run extraction flow"""

    def __init__(self, **kwargs: dict) -> None:
        self.util_inputs = Helpers(**kwargs).validate_extraction_parameters()
        self.run_dir = self.util_inputs.get('run_dir')
        self.cell_name = self.util_inputs.get('cell_name')
        self.waiveoff_lvs_errors = self.util_inputs.get('waiveoff_lvs_errors')
        self.lvs_set = self.util_inputs.get('lvs_settings')
        self.layout_filepath = self.util_inputs.get('layout_filepath')
        self.schematic_filepath = self.util_inputs.get('schematic_filepath')
        self.extract_settings = self.util_inputs.get('extract_settings')
        self.lvs_tool_name = self.util_inputs.get('lvs_tool_name')
        self.extract_tool = self.util_inputs.get('extract_tool')
        self.layout = ''
        self.netlist = ''
        self.kwargs = kwargs
        if not self.schematic_filepath:
            netlist_ret_code, self.netlist = self.netlist_creation()
            self.extract_settings['netlist'] = self.netlist
            self.lvs_set['netlist'] = self.netlist
            if netlist_ret_code != 0:
                logging.error('Netlist file creation failed for %s', self.cell_name)
                raise ValueError(f'Netlist file not found for {self.cell_name}')
        else:
            self.netlist = self.util_inputs.get('schematic_filepath')

        if not self.layout_filepath:
            oasis_ret_code, self.layout = self.oasis_layout_creation()
            self.lvs_set['layout'] = self.layout
            if oasis_ret_code != 0:
                logging.error('Oasis file Conversion failed for %s', self.cell_name)
                raise ValueError(f'Layout file not found for {self.cell_name}')
        else:
            self.layout = self.util_inputs.get('layout_filepath')

    def netlist_creation(self) -> tuple:
        """Generates netlist from schematic of cell by converting OA to CDL

                Returns
                -------
                si_return_code : int
                    This gives the return code for successful run of Si tool
                netlist_file :
                    This returns generated netlist file

                Raises
                ------
                RuntimeError :
                    Raised if there are issues in tool run or tool object creation
                OSError :
                    Raised if the file is not present in given path
                FileNotFoundError :
                    Raised if netlist file is not found
                """

        try:
            netlist_tool = si.Si(**self.util_inputs.get('si_settings'))
            si_return_code, _, _ = netlist_tool.run()
            netlist_file = Path(self.run_dir) / f'{self.cell_name}.cdl'
            if not netlist_file.exists():
                logging.error('There is some issue in creation of Netlist from schematic of cell '
                              '%s', self.cell_name)
                raise FileNotFoundError(f'Netlist File is not generated for cell {self.cell_name}')
            logging.info('Netlist file %s is generated from schematic of cell %s',
                         netlist_file, self.cell_name)
            return si_return_code, netlist_file
        except (OSError, RuntimeError) as error:
            raise error

    def oasis_layout_creation(self) -> tuple:
        """Create oasis file(.oa format) from layout of cell.
            Convertion of OA to OASIS Layout
                Returns
                -------
                oasis_return_code : int
                    This gives the return code for successful run of Oasis file creation tool
                oasis_file :
                    This returns generated oasis file path

                Raises
                ------
                RuntimeError :
                    Raised if there are issues in tool run or tool object creation
                FileNotFoundError :
                    Raised if generated file is not found
                """

        try:
            logging.info('Creating OASIS layout from pcell layout of cell %s', self.cell_name)
            oasisout_tool = oasisout.OasisOut(**self.util_inputs.get('oasis_out_settings'))
            oasis_return_code, _, _ = oasisout_tool.run()
            oasis_file = Path(self.run_dir) / f'{self.cell_name}.oas'
            if not oasis_file.exists():
                logging.error('There is some issue in generation of Oasis layout file from oa '
                              'layout for cell %s', self.cell_name)
                raise FileNotFoundError(f'Oasis File is not generated for cell {self.cell_name}')
            logging.info('Oasis layout file %s is generated from oa layout for cell %s',
                         oasis_file, self.cell_name)
            return oasis_return_code, oasis_file
        except (RuntimeError, FileNotFoundError) as error:
            raise error

    def setup_smc(self) -> None:
        """Generate smcpair.cmd and corners.defines files.

        Parameters
        ----------
        data : dict
            Key-value pair data.
        kit : Kit
            Kit object.
        ext_run_dir : str
            StarRC run directory path.
        """
        # Section: condition
        temperature = self.kwargs.get('temp_list').split(',')
        skew = self.kwargs.get('skew_list').split(',')

        # Section: eda
        is_native = self.extract_settings.get('native_star')
        smcpair = True

        # SMC
        corners_defines_file = None
        if not corners_defines_file:
            corners_defines_file = str(Path(self.run_dir) / 'corners.defines')
            utils.generate_corners_defines(
                corners_defines_file=corners_defines_file,
                nxtgrd_path=str(Path(self.extract_settings.get('kit').get_component_path(code='extraction_starrc_techfiles'))),
                smcpair=smcpair,
                has_vcf=False,
                is_native=is_native,
                is_asic=False,
                temperature_list=temperature,
                skew_list=skew
            )

        utils.generate_smc_cmd_file(
            smc_cmd_file=str(Path(self.run_dir) / 'smcpair.cmd'),
            corners_defines_file=corners_defines_file
        )

    def lvs(self, netlist, layout) -> tuple:
        """Perform layout vs schematic check
                Parameters
                ----------
                netlist :
                    Netlist file generated from Si tool
                layout :
                    Oasis file generated from OasisOut module

                Returns
                -------
                lvs_return_code :
                    Return integer code for LVS tool run
                layout_err_status :
                    Status as pass/fail based on the layout errors if any
                lvs_err_status :
                    Status as pass/fail based on the lvs errors if any
                Raises
                ------
                ValueError
                    Raised if layout file, runsets, or libcells not found.
                FileNotFoundError
                    Raised if lvs log file not found
                Exception
                    Raised in case of any missed exception
                """
        try:
            logging.info('Performing layout vs schematic check for cell %s', self.cell_name)
            if not (netlist and layout):
                logging.error('Netlist/Layout File is not found for cell %s while performing LVS',
                              self.cell_name)
                raise FileNotFoundError('Missing Netlist/ Layout File for LVS for cell %s',
                                        self.cell_name)

            # Defining imports for different lvs tool names
            if self.lvs_tool_name == 'icv':
                from waldo.tool.icv import lvs  # pylint: disable=import-outside-toplevel
            elif self.lvs_tool_name == 'calibre':
                from waldo.tool.calibre import lvs  # pylint: disable=import-outside-toplevel
            elif self.lvs_tool_name == 'pvs':
                from waldo.tool.pvs import lvs  # pylint: disable=import-outside-toplevel
            elif self.lvs_tool_name == 'pegasus':
                from waldo.tool.pegasus import lvs  # pylint: disable=import-outside-toplevel
            else:
                pass  # Need to implement later in case new tool comes in picture

            lvs_tool = lvs.Lvs(**self.lvs_set)
            lvs_return_code, _, _ = lvs_tool.run()
            layout_err_status = lvs_tool.layout_errors().status
            lvs_err_status = lvs_tool.lvs_errors().status
            lvs_log = str(Path(self.run_dir) / lvs_tool._to_logfile)
            if not lvs_log:
                logging.error('Error in generating LVS log file for cell %s', self.cell_name)
                raise FileNotFoundError(f'LVS log not found for cell {self.cell_name}')

            logging.info('LVS log file for cell %s is generated: %s', self.cell_name, lvs_log)
            return lvs_return_code, layout_err_status, lvs_err_status
        except ValueError as error:
            logging.exception('Exception raised while performing LVS for cell %s: %s',
                              self.cell_name, error)
            raise error
        except Exception as error:
            raise error

    def extract(self) -> tuple:
        """Extraction using extraction tool
                Parameters
                ----------
                netlist :
                    Netlist file path
                Returns
                -------
                extract_return_code :
                    Returns te return code if any issues while extraction takes place using StarRC
                spf_exist :
                    Returns True/False based on presence of spf file
                sum_exist :
                    Returns True/False based on presence of summary file
                Raises
                ------
                Exception
                    Raised exceptions ValueError, RunTimeError,
                    NoStarRcXtToolVersionError and StarRcXtToolSetupError in starRC module
                """
        try:
            extract_tool_obj, extract_return_code, spf_exist, sum_exist = '', 1, False, False
            logging.info('Performing RC extraction for cell %s', self.cell_name)
            if self.extract_tool == 'starrc':
                from waldo.tool import starrcxt  # pylint: disable=import-outside-toplevel
                extract_tool_obj = starrcxt.StarRC(**self.extract_settings)
            elif self.extract_tool == 'qrc':
                from waldo.tool import qrc  # pylint: disable=import-outside-toplevel
                extract_tool_obj = qrc.Qrc(**self.extract_settings)
            else:
                pass  # Need to implement in case of new addition to extract tool
            if self.schematic_filepath and self.layout_filepath:
                cmd_file = Path(self.run_dir) / 'star_native_rendered.cmd'
                if cmd_file.exists():
                    for line in fileinput.input(str(cmd_file), inplace=1):
                        line = line.replace('OA_CDLOUT_RUNDIR', '** OA_CDLOUT_RUNDIR')
                        sys.stdout.write(line)

            extract_return_code, _, _ = extract_tool_obj.run()
            if extract_return_code != 0:
                logging.error('Extraction for cell %s is failing with return code %d',
                              self.cell_name, extract_return_code)
                raise RuntimeError(f'Extraction failed for cell {self.cell_name}')

            spf_exist = Path(extract_tool_obj.spf_file).exists() if not self.util_inputs.get(
                'write_oa') else True
            sum_exist = Path(extract_tool_obj.sum_file).exists()
            return extract_return_code, spf_exist, sum_exist
        except Exception as error:
            logging.exception("Exception in extraction for cell %s: %s", self.cell_name, error)
            raise error

    def run(self) -> tuple:
        """ Main method to run complete extraction
            Returns
                -------
                extract_ret_code :
                    Returns the return code if any issues while extraction takes place using StarRC
                spf_exist :
                    Returns True/False based on presence of spf file
                sum_exist :
                    Returns True/False based on presence of summary file
                Raises
                ------
                Exception
                    Raised if any exception is there
        """
        try:
            ndm_dbpath = self.kwargs.get('ndm_dbpath')
            def_filepath = self.kwargs.get('def_filepath')
            extract_ret_code, spf_exist, sum_exist = 1, False, False
            if not (ndm_dbpath or def_filepath):
                lvs_return_code, layout_err_status, lvs_err_status = self.lvs(self.netlist,
                                                                              self.layout)

                if lvs_return_code != 0:
                    logging.error('Error occurred while performing LVS, return code is %d',
                                  lvs_return_code)
                    raise RuntimeError(f'LVS has some issues for cell {self.cell_name}')
                if self.extract_settings.get('smc'):
                    self.setup_smc()
                    generated_smc_cmd_file = str(Path(self.run_dir) / 'smcpair.cmd')
                    self.extract_settings.update({
                        'overrides_cmd_files':[generated_smc_cmd_file],
                    })
                if ((layout_err_status == 'pass' and lvs_err_status == 'pass') or
                        self.waiveoff_lvs_errors):
                    extract_ret_code, spf_exist, sum_exist = self.extract()
                    if self.util_inputs.get('write_oa'):
                        self.extract_settings.update({'write_oa': False})
                        extract_ret_code, spf_exist, sum_exist = self.extract()
                    logging.info('Extraction successfully performed for cell %s', self.cell_name)
                else:
                    logging.error('Failure with layout error as %s, lvs error as %s and waive off '
                                  'option as %s for cell %s', layout_err_status, lvs_err_status,
                                  self.waiveoff_lvs_errors, self.cell_name)
            else:
                extract_ret_code, spf_exist, sum_exist = self.extract()
            return extract_ret_code, spf_exist, sum_exist
        except Exception as error:
            raise error
