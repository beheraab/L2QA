""" This module provides the API to run the post and prelayout simulations"""

import logging
import getpass
import os
import glob
import shutil
import re
from pathlib import Path
from waldo.util import template
from waldo.model import Kit,ToolExec
from waldo.tool.virtuoso import Virtuoso
from waldo.tool.ocean import Ocean
from pdk_environment.envsetup.pdkconfig import get_layer_stack
from .helpers import Helpers

class LpePolo:
    """ Module to run post and prelayout simulation"""

    def __init__(self, **kwargs: dict):
        """ Initialize Simulation

        keyword Arguments
        ----------
        kwargs: Dict, Required
            inputs data required of simulation from the input yaml file
            kit_name, tech_opt, lib_name, cell_name, temperature, skew,
            polo_element, test_patter, wait_on, cds_lib

        Returns:
        Object -> Object
        """
        Helpers(**kwargs).validate_lvs_tool_name()
        self._kwargs = kwargs

        logging.info("input parameters: %s", kwargs)
        self.kit_name = self._kwargs.get('kit_name')
        self.tech_opt = self._kwargs.get('tech_opt')
        self.lib_name = self._kwargs.get('lib_name')
        self.cell_name = self._kwargs.get('cell_name')
        self.temperature = self._kwargs.get('temperature')
        self.skew = self._kwargs.get('skew')
        self.polo_element = self._kwargs.get('polo_element')
        self.cds_lib = self._kwargs.get('cds_lib_filepath')
        self.extract_dir = self._kwargs.get('extract_dir')



        try:
            if not Path(self.extract_dir).exists():
                logging.error('Extract Directory not found')
                raise FileNotFoundError
        except Exception as error:
            logging.exception('Extract directory not found %s', error)
            raise error

        self.kit = Kit.get(self.kit_name, self.tech_opt)
        self.run_dir = self._kwargs.get('run_directory')


        try:
            if Path(str(Path(self.extract_dir) / f'{self.cell_name}.spf')).exists():
                self.spf_file = str(Path(self.extract_dir) / f'{self.cell_name}.spf')
        except Exception as error:
            logging.exception('spf file not found %s', error)
            raise error
        

        models_dir_string = self.kit.root
        models_dir_string += "/models"

        model_library = os.path.join(models_dir_string, '**', '*.scs')
        self.model_files = glob.glob(model_library, recursive=True)

        self.layerstack = get_layer_stack(self.kit_name)
        if self._kwargs.get('lvs_tool_name') == 'icv':
            self.flow = 'icv_starrcxt'
        elif self._kwargs.get('lvs_tool_name') == 'calibre':
            self.flow = 'calibre_starrcxt'

        if self._kwargs.get('extraction_view') == 'oa':
            self.view = self.flow+"."+self._kwargs.get('skew')+"."+str(self._kwargs.get('temperature'))
        elif self._kwargs.get('extraction_view') == 'smc-oa':
            self.view ="smc-"+self.flow+"."+"separate_typ_nom"

    def generate_spectre_netlist(self):
        """ Creates netlist generation file in rundir and
        run it to generate spectre netlist

        Returns:
        --------
            None
        """
        if (Path(self.run_dir).absolute()/'netlist_convert').exists():
            os.remove(Path(self.run_dir).absolute()/'netlist_convert')

        logging.info('Generating netlist convert file...')
        settings = {
            'src_file': str(Path(__file__).parent / 'templates' / 'netlist_convert.j2'),
            'dst_file': str(Path(self.run_dir) / 'netlist_convert'),
            'values':{
                'simualtion_path' :str(Path(self.run_dir) / 'simulation') ,
                'lib_name' : self.lib_name,
                'cell_name' : self.cell_name
            }
        }
        _, undefined = template.generate(**settings)
        if len(undefined) != 0:
            raise RuntimeError(f'Undefined variables while setting up options: {str(undefined)}')

        try:
            tool = Virtuoso(kit=self.kit,
                    cmd='/p/foundry/env/proj_tools/iqt/current/SUPPORT/run_with_virtual_fb',
                    options=f'--quiet virtuoso -noxshm -nograph -replay {self.run_dir}/netlist_convert' \
                            f' -log {self.run_dir}/netlist_convert.log',
                    cds_lib = self.cds_lib,
                    component_type ='pcell',
                    run_dir=self.run_dir)
            netlist_return_code, netlist_out, _ = tool.run()
            return netlist_return_code, netlist_out
        except Exception as error:
            logging.exception("Error while running spectre netlist - %s", error)
            raise error

    def generate_pre_polo_netlist(self):
        """ Generate netlist_prelay and netlist_polo

        raises
        ------
        FileNOFoundError:
            if netlist file is not available it will raise error
        """
        netlist_path=f"{self.run_dir}/simulation/{self.cell_name}/spectre/schematic/netlist/netlist"
        if not Path(netlist_path).exists():
            raise FileNotFoundError('Netlist file is not found/generated')

        logging.info("Generating netlis_prelay from spectre netlist")
        try:
            if not Path(f"{self.run_dir}/simulation/{self.cell_name}/spectre/schematic/netlist/"\
                "netlist_prelay").exists():
                shutil.copy2(netlist_path,f"{self.run_dir}/simulation/{self.cell_name}/spectre/"\
                    "schematic/netlist/netlist_prelay")
        except Exception as error:
            logging.exception('Exception occured while creating netlist_prelay')
            raise error

        # creating netlist_polo with netlist_prelay
        logging.info("Generating netlis_polo from spectre netlist")
        try:
            with open(f"{self.run_dir}/simulation/{self.cell_name}/spectre/schematic/netlist/"\
                "netlist_prelay", 'r', encoding='utf8') as net_pre:
                netlist_polo_lines = [''.join(['//',x.strip(), '\n']) for x in net_pre.readlines()]

            with open(f"{self.run_dir}/simulation/{self.cell_name}/spectre/schematic/netlist/"\
                "netlist_polo", 'w', encoding='utf8') as net_polo:
                net_polo.writelines(netlist_polo_lines)
        except Exception as error:
            logging.exception('Exception occured while creating netlist_prelay')
            raise error

    def get_terminal_netlist(self, netlist_path) -> list:
        """  Returns the terminal netlist of list values

        Returns
        -------
        terminal_netlist: list
            list of netlist from the spectre netlist file
        """
        def _get_nelist(file_name:str,expression:str) -> list:
            terminal_net = []
            with open(file_name, 'r', encoding='utf8') as file:
                for line in file.readlines():
                    match = re.match(expression, line, re.DOTALL)
                    if match:
                        netlists = line.split()
                        netlists.pop(0)
                        for each in netlists:
                            each = each.strip('()')
                            terminal_net.append(each)
            return terminal_net

        logging.info("Preparing terminal netlist from the netlist file...")
        try:
            terminal_netlist = _get_nelist(netlist_path,r'[Ll]') if self.polo_element == 'ind'\
                else _get_nelist(netlist_path,r'^[Ii]')
        except Exception as error:
            logging.exception("Error while generating terminal spectre netlist file :%s",error)
            raise error

        return terminal_netlist

    def get_subckt_terminals(self) -> list:
        """ Identifying terminal names in SPF file subckt definition and this
        code assume the  terminal names will match with spectre netlist. This
        script do not do a cross check between spectre netlist terminal names
        and spf subckt terminal names.
        Returns
        -------
        subckt_terminals: list
            list of termina names from the spf file
        """
        logging.info("Preparing Sub Circuit(subckt) teminal values from spf file....")
        subckt_terminals = []
        try:
            with open(self.spf_file, 'r', encoding='utf8') as file:
                for line in file.readlines():
                    if '.SUBCKT' in line:
                        subckt_list = line.split()
                        subckt_terminals.extend(subckt_list)
        except Exception as error:
            logging.exception("Error while generating subcircuit list from spf file %s", error)
            raise error


        return subckt_terminals

    def _get_model_data(self) -> list:
        """ Returns the list of model files under the given kit
        Returns
        -------
        modelfiles_data: list
            list of model files data
        """
        # This block will return the list of model files in the kit root based on the logic
        # Logic is ported from perl script. Code is working fine and producing expected output

        process = self.kit.tech
        logging.info("Generating modelfile list for process %s",process)
        modelfiles_data = []
        if process == "1271":
            for file in self.model_files:
                all_file_list = file.split('/')
                if ((re.search('devpar', all_file_list[-1])) \
                    or (re.search('aging', all_file_list[-2]))):
                    continue
                if any(True for val in ["primtemplate.scs", "mfc.scs", "ind.scs", "ind_scl.scs",
                "indwrapper_scl.scs", "var.scs"] if re.search(val, all_file_list[-1])):
                    continue
                if all_file_list[-1] == "esd.scs":
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                else:
                    modelfiles_data.append(f"    '(\"{file}\" \"tttt\")\n")

        if process == "1273":
            for file in self.model_files:
                all_file_list = file.split('/')
                if re.search('aging', all_file_list[-2]):
                    continue
                if re.search("intel73custom.scs",all_file_list[-1]):
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                elif re.search("p1273_6_halftcnr.scs",all_file_list[-1]):
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                elif re.search("intel73indwrapper.scs",all_file_list[-1]):
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                elif re.search("intel73mfccustom.scs",all_file_list[-1]):
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                elif re.search("intel73mfcwrapper.scs",all_file_list[-1]):
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                elif re.search("intel73prim.scs",all_file_list[-1]):
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                else:
                    modelfiles_data.append(f"    '(\"{file}\" \"tttt\")\n")

        if process == "1222":
            for file in self.model_files:
                all_file_list = file.split('/')
                if re.search(self.layerstack[self.tech_opt], file):
                    if re.search("common", all_file_list[-2]):
                        continue
                    if re.search(f"p1222_{self.kit.dot}.scs", file):
                        modelfiles_data.append(f"    '(\"{file}\" \"tttt\")\n")
                elif re.match(f"^{self.layerstack[self.tech_opt]}", file):
                    if re.search('aging', file):
                        continue
                    if (re.search('var_be.scs', all_file_list[-1]) \
                        or re.search('var_fe.scs', all_file_list[-1])):
                        continue
                    if re.search("intel73custom.scs",all_file_list[-1]):
                        modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                    elif re.search(r"p1222_[0-9]+_degpar.scs",all_file_list[-1]):
                        modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                    elif re.search(r"p1222_[0-9]+_eos.scs",all_file_list[-1]):
                        modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                    elif re.search("bitcells.scs",all_file_list[-1]):
                        modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                    else:
                        modelfiles_data.append(f"    '(\"{file}\" \"tttt\")\n")

        if process == "1272":
            for file in self.model_files:
                all_file_list = file.split('/')
                if re.search('aging', all_file_list[-3]):
                    continue
                if re.search('sram', all_file_list[-3]):
                    continue
                if (re.search('var_be.scs', all_file_list[-1]) \
                    or re.search('var_fe.scs', all_file_list[-1])):
                    continue
                if re.search("c8lib6.scs",all_file_list[-1]):
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                elif re.search(r"p1222_[0-9]+_degpar.scs",all_file_list[-1]):
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                elif re.search(r"p1222_[0-9]+_eos.scs",all_file_list[-1]):
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                else:
                    modelfiles_data.append(f"    '(\"{file}\" \"tttt\")\n")

        if process == "1276":
            for file in self.model_files:
                all_file_list = file.split('/')
                if re.search('aging', all_file_list[-3]):
                    continue
                if re.search('sram', all_file_list[-3]):
                    continue
                if (re.search('var_be.scs', all_file_list[-1]) \
                    or re.search('var_fe.scs', all_file_list[-1])):
                    continue
                if re.search("intel76custom.scs",all_file_list[-1]):
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                else:
                    modelfiles_data.append(f"    '(\"{file}\" \"tttt\")\n")

        if process == "1278":
            for file in self.model_files:
                all_file_list = file.split('/')
                #To Do: Ned to work
                if re.search(self.layerstack[self.tech_opt], file):
                    modelfiles_data.append(f"    '(\"{file}\" \"tttt\")\n")
                elif re.search("intel78custom.scs",file):
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                else:
                    continue

        if process == "1277":
            for file in self.model_files:
                all_file_list = file.split('/')
                #To Do: Need to work
                if re.search(self.layerstack[self.tech_opt], file):
                    modelfiles_data.append(f"    '(\"{file}\" \"tttt\")\n")
                elif re.search("intel77custom.scs",file):
                    modelfiles_data.append(f"    '(\"{file}\" \"\")\n")
                else:
                    continue

        return modelfiles_data


    def run_ro_ocean_prelay(self):
        """ script used to run the pre-layout simulation
        returns
        --------
            prelay_exitcode : int
                prelayout simulation exitcode either 0 or 1, 0 for successfull.
                other than 0 will be failure.
        """
        netlist_path=f"{self.run_dir}/simulation/{self.cell_name}/spectre/"\
            "schematic/netlist/netlist"
        results_path=f"{self.run_dir}/simulation/{self.cell_name}/spectre/schematic"
        netlist_prelay = f"{self.run_dir}/simulation/{self.cell_name}/spectre/"\
            "schematic/netlist/netlist_prelay"
        subckt_terminal = self.get_subckt_terminals()
        terminal_netlist = self.get_terminal_netlist(netlist_prelay)
        #genrating scs file
        logging.info('Generating testbench file tb_prelay.scs for prelayout simulation')
        tb_prelay_settings = {
            'src_file': str(Path(__file__).parent / 'templates' / 'tb_prelay.scs.j2'),
            'dst_file': str(Path(self.run_dir) / 'tb_prelay.scs'),
            'values': {
                'subckt_terminal' : subckt_terminal,
                'lvs_tool' : self._kwargs.get("lvs_tool_name")

            }
        }
        _, undefined = template.generate(**tb_prelay_settings)
        if len(undefined) != 0:
            raise RuntimeError(f'Undefined variables while setting up options: {str(undefined)}')

        #model file data to put in ocn script
        modelfiles_data = self._get_model_data()
        modelfiles_data.append(f"    '(\"{self.run_dir}/tb_prelay.scs\")\n")

        # generate ocn file
        logging.info("Generating tb_prelay ocn file for prelayput simulation.")
        settings = {
            'src_file': str(Path(__file__).parent / 'templates' / 'ocn' / 'run_ro.ocn.j2'),
            'dst_file': str(Path(self.run_dir) / 'run_prelay.ocn'),
            'values': {
                'netlist_path': netlist_path,
                'results_path': results_path,
                'model_files': ' '.join(map(str,modelfiles_data)),
                'outfile_handle': f"{self.run_dir}/{self.cell_name}.out",
                'testcaseval': f"{self.cell_name} (prelay)",
                'net_name1': terminal_netlist[1],
                'net_name2': subckt_terminal[3]
            }
        }
        _, undefined = template.generate(**settings)
        if len(undefined) != 0:
            raise RuntimeError(f'Undefined variables while setting up options: {str(undefined)}')

        #running prelayout simulation
        logging.info('Preparing for prelayout simulation..')
        try:
            tool = Ocean(kit=self.kit,
                    cmd='ocean',
                    options= f"-noxshm -log {self.run_dir}/run_prelay.ocn.log"\
                            f" -replay {self.run_dir}/run_prelay.ocn",
                    run_dir=self.run_dir)
            
            prelay_exitcode, prelay_stdout, _ = tool.run()
        except Exception as error:
            logging.exception("Error while running pre layout simulation: %s", error)
            raise error
        logging.info('Writing standard output in run_prelay.ocn.stdout')
        with open(Path(f"{self.run_dir}/run_prelay.ocn.stdout"), 'w',
            encoding='utf8') as pre_stdout:
            pre_stdout.writelines(prelay_stdout)

        return prelay_exitcode

    def run_ro_ocean_polo(self):
        """ script used to run the post layout simulation
        returns
        --------
            polo_exitcode : int
                post simulation exitcode either 0 or 1, 0 for successfull.
                other than 0 will be failure
        """

        netlist_path=f"{self.run_dir}/simulation/{self.cell_name}/spectre/schematic/"\
        "netlist/netlist"
        results_path=f"{self.run_dir}/simulation/{self.cell_name}/spectre/schematic"

        if Path(f"{self.run_dir}/simulation/{self.cell_name}/spectre/schematic/netlist/netlist_polo").exists():
            shutil.copy2(f"{self.run_dir}/simulation/{self.cell_name}/spectre/schematic/netlist/netlist_polo",
                netlist_path)

        netlist_prelay = f"{self.run_dir}/simulation/{self.cell_name}/spectre/"\
            "schematic/netlist/netlist_prelay"
        subckt_terminal = self.get_subckt_terminals()
        terminal_netlist = self.get_terminal_netlist(netlist_prelay)

        logging.info("Generating testbench file for post layout simulation")
        try:
            if Path(f"{self.run_dir}/tb_prelay.scs").exists():
                if Path(f"{self.run_dir}/tb_polo.scs").exists():
                    os.remove(Path(self.run_dir).absolute() / 'tb_polo.scs')
                with open(Path(f"{self.run_dir}/tb_prelay.scs"), 'r', encoding='utf8') as tb_prelay:
                    tb_polo_lines = [''.join([x.replace('//I_polo','I_polo')]) \
                        for x in tb_prelay.readlines()]

                with open(Path(f"{self.run_dir}/tb_polo.scs"), 'w', encoding='utf8') as tb_polo:
                    tb_polo.writelines(tb_polo_lines)
        except Exception as error:
            logging.exception('Error while creating tb_polo.scs file %s', error)
            raise error

        #model file data to put in polo ocn script
        modelfiles_data = self._get_model_data()
        modelfiles_data.append(f"    '(\"{self.spf_file}\" \"\")\n")
        modelfiles_data.append(f"    '(\"{self.run_dir}/tb_polo.scs\")\n")

        #template setting for run_polo.ocn jinja2
        logging.info('generating run_polo.ocn file')
        settings = {
            'src_file': str(Path(__file__).parent / 'templates' / 'ocn' / 'run_ro.ocn.j2'),
            'dst_file': str(Path(self.run_dir) / 'run_polo.ocn'),
            'values': {
                'netlist_path': netlist_path,
                'results_path': results_path,
                'model_files': ' '.join(map(str,modelfiles_data)),
                'outfile_handle': f"{self.run_dir}/{self.cell_name}.out",
                'testcaseval': f"{self.cell_name} (polo)",
                'net_name1': terminal_netlist[1],
                'net_name2': subckt_terminal[3]
            }
        }
        _, undefined = template.generate(**settings)
        if len(undefined) != 0:
            raise RuntimeError(f'Undefined variables while setting up options: {str(undefined)}')


        #running post simulation
        logging.info('Preparing post layout simulation..')
        try:
            tool = Ocean(kit=self.kit,
                    cmd='ocean',
                    options=f"-noxshm -log {self.run_dir}/run_polo.ocn.log" \
                        f" -replay {self.run_dir}/run_polo.ocn",
                    run_dir=self.run_dir)
            polo_exitcode, polo_stdout, _ = tool.run()
        except Exception as error:
            logging.exception('Error while running post layout simulation: %s', error)
            raise error
        logging.info('Writing standard output in run_polo.ocn.stdout')
        with open(Path(f"{self.run_dir}/run_polo.ocn.stdout"), 'w', encoding='utf8') as polo_out:
            polo_out.writelines(polo_stdout)
        return polo_exitcode

    def run_ro_ocean_oa(self):
        """ Creating testbench and ocean script for ring oscillator OA simulation.
        returns
        --------
            polo_oa_exitcode : int
                polo oa simulation exitcode either 0 or 1, 0 for successfull.
                other than 0 will be failure
        """
        design_block = f'{getpass.getuser()}_p{self.kit.dot}" "{self.cell_name}" "{self.view}'
        results_path=f"{self.run_dir}/simulation/{self.cell_name}/spectre/schematic"
        netlist_path = f"{self.run_dir}/simulation/{self.cell_name}/spectre/"\
            "schematic/netlist/netlist_prelay"
        subckt_terminal = self.get_subckt_terminals()
        terminal_netlist = self.get_terminal_netlist(netlist_path)
        modelfiles_data = self._get_model_data()
        modelfiles_data.append(f"    '(\"{self.run_dir}/tb_prelay.scs\")\n")

        logging.info("Generating run_oa ocn file for oa view simulation.")
        settings = {
            'src_file': str(Path(__file__).parent / 'templates' / 'ocn' / 'run_ro.ocn.j2'),
            'dst_file': str(Path(self.run_dir) / 'run_oa.ocn'),
            'values': {
                'netlist_path': design_block,
                'results_path': results_path,
                'model_files': ' '.join(map(str,modelfiles_data)),
                'outfile_handle': f"{self.run_dir}/{self.cell_name}.out",
                'testcaseval': f"{self.cell_name} (oa)",
                'net_name1': terminal_netlist[1],
                'net_name2': subckt_terminal[3]
            }
        }
        _, undefined = template.generate(**settings)
        if len(undefined) != 0:
            raise RuntimeError(f'Undefined variables while setting up options: {str(undefined)}')

        #running oa simulation
        logging.info('Preparing for post layout simulation of oa view..')
        try:
            tool = Ocean(kit=self.kit,
                    cmd='ocean',
                    options=f"-noxshm -log {self.run_dir}/run_oa.ocn.log" \
                        f" -replay {self.run_dir}/run_oa.ocn",
                    run_dir=self.run_dir)
            polo_oa_exitcode, polo_stdout, _ = tool.run()
        except Exception as error:
            logging.exception("Error while running oa simulation: %s", error)
            raise error
        logging.info('Writing standard output in run_oa.ocn.stdout')
        with open(Path(f"{self.run_dir}/run_oa.ocn.stdout"), 'w',
            encoding='utf8') as oa_stdout:
            oa_stdout.writelines(polo_stdout)

        return polo_oa_exitcode

    def run_ro_ocean_smc_oa(self):
        """ Creating testbench and ocean script for ring oscillator SMC OA simulation.
        returns
        --------
            polo_smc_oa_exitcode : int
                polo smc-oa simulation exitcode either 0 or 1, 0 for successfull.
                other than 0 will be failure
        """
        design_block = f'{getpass.getuser()}_p{self.kit.dot}" "{self.cell_name}" "{self.view}'
        results_path=f"{self.run_dir}/simulation/{self.cell_name}/spectre/schematic"
        netlist_path = f"{self.run_dir}/simulation/{self.cell_name}/spectre/"\
            "schematic/netlist/netlist_prelay"
        subckt_terminal = self.get_subckt_terminals()
        terminal_netlist = self.get_terminal_netlist(netlist_path)
        modelfiles_data = self._get_model_data()
        modelfiles_data.append(f"    '(\"{self.run_dir}/tb_prelay.scs\")\n")

        logging.info("Generating run_smc_oa ocn file for smc oa view simulation.")
        settings = {
            'src_file': str(Path(__file__).parent / 'templates' / 'ocn' / 'run_ro.ocn.j2'),
            'dst_file': str(Path(self.run_dir) / 'run_smc_oa.ocn'),
            'values': {
                'netlist_path': design_block,
                'results_path': results_path,
                'model_files': ' '.join(map(str,modelfiles_data)),
                'outfile_handle': f"{self.run_dir}/{self.cell_name}.out",
                'testcaseval': f"{self.cell_name} (smc-oa)",
                'net_name1': terminal_netlist[1],
                'net_name2': subckt_terminal[3]
            }
        }
        _, undefined = template.generate(**settings)
        if len(undefined) != 0:
            raise RuntimeError(f'Undefined variables while setting up options: {str(undefined)}')

        #running  smc oa simulation
        logging.info('Preparing smc oa simulation for smc oa view...')
        try:
            tool = Ocean(kit=self.kit,
                    cmd='ocean',
                    options=f"-noxshm -log {self.run_dir}/run_smc_oa.ocn.log" \
                        f" -replay {self.run_dir}/run_smc_oa.ocn",
                    run_dir=self.run_dir)
            smc_oa_exitcode, smc_oa_stdout, _ = tool.run()
        except Exception as error:
            logging.exception("Error while running oa simulation: %s", error)
            raise error
        logging.info('Writing standard output in run_smc_oa.ocn.stdout')
        with open(Path(f"{self.run_dir}/run_smc_oa.ocn.stdout"), 'w',
            encoding='utf8') as oa_stdout:
            oa_stdout.writelines(smc_oa_stdout)

        return smc_oa_exitcode

    def run(self) -> tuple:
        """ Main method to run complete pre layout and post layout
            Returns
                -------
                prelay_ret_code :
                    Returns te return code of prelayout simulation
                polo_ret_code :
                    Returns return code of post layout simulation based on the extraction view used

                Raises
                ------
                Exception
                    Raised if any exception is there
        """
        try:
            return_code = None
            return_string = ''
            if self._kwargs.get('extraction_view') == 'oa':
                self.generate_spectre_netlist()
                self.generate_pre_polo_netlist()
                self.run_ro_ocean_prelay()
                self.run_ro_ocean_oa()
                return_code, return_string = self.check_error_in_output()

            elif self._kwargs.get('extraction_view') == 'smc-oa':
                self.generate_spectre_netlist()
                self.generate_pre_polo_netlist()
                self.run_ro_ocean_prelay()
                self.run_ro_ocean_smc_oa()
                return_code, return_string = self.check_error_in_output()

            else:
                self.generate_spectre_netlist()
                self.generate_pre_polo_netlist()
                self.run_ro_ocean_prelay()
                self.run_ro_ocean_polo()
                return_code, return_string = self.check_error_in_output()
            logging.info("Simulations is %s  by returning %s",(return_string, return_code))
            return return_code, return_string
        except Exception as error:
            raise error

    def check_error_in_output(self):
        """ this method will read the simulation output file

        returns:
            return_code: int,
                return 0 if no error found else 1
            return_string: str,
                 returns error messages if any

        """
        try:
            return_code = 0
            return_string = "Pass"
            with open(Path(f"{self.run_dir}/{self.cell_name}.out"), 'r', encoding='utf8') as out_file:
                for line in out_file.readlines():
                    if re.match("ERROR from runPath", line):
                        return_string = "ERROR: ocean run() script produced an error in "\
                                f"{self.run_dir}/{self.cell_name}.out"
                        return_code = 1

                    if re.match("ERROR from transientResult", line):
                        return_string = "ERROR: ocean selectResult() script"\
                                f" produced an error in {self.run_dir}/{self.cell_name}.out"
                        return_code = 1

                    if re.match("freq\=ERROR", line):
                        return_string = f"ERROR:  an error occured  in {self.run_dir}/{self.cell_name}.out"
                        return_code = 1
            return return_code, return_string
        except Exception as error:
            raise error
