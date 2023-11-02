"""Module to run isotope"""
import os
import getpass
import shutil
import re
from pathlib import Path
import logging
from waldo.model import Kit
from waldo.tool.virtuoso import Virtuoso


class Isotope:
    """Base class to initialize the data
    and run test pattern based on user input"""

    def __init__(self, **kwargs):
        """Method to initialize the data
        Args
        -----
        required args"""
        self._kwargs = kwargs
        self.lvs_tools = ('icv', 'calibre', 'pvs', 'pegasus')
        self.lvs_tool_name = self._kwargs.get('lvs_tool_name')
        if self.lvs_tool_name not in self.lvs_tools:
            raise Exception("lvs tool not supported or lvs tool attribute is empty")
        self.kit_name = self._kwargs.get('kit_name')
        self.cell_name = self._kwargs.get('cell_name')
        self.temperature = self._kwargs.get('temperature')
        self.skew = self._kwargs.get('skew')
        self.run_directory = self._kwargs.get('run_directory')
        self.extract_dir = self._kwargs.get('extract_dir')
        self.Isotope_extra = self._kwargs.get('Isotope_extra')
        self.exclude_list = set()
        if str(self.Isotope_extra).startswith("ignore"):
            self.exclude_list.update(self.Isotope_extra.split(" ")[1].split(","))

        self.spf_vs_spf = self._kwargs.get('spf_vs_spf')
        self.oa_vs_spf = self._kwargs.get('oa_vs_spf')
        if not self.spf_vs_spf and not self.oa_vs_spf:
            raise Exception("Comparison type is not specified(oa_vs_spf)/(spf_vs_spf)")
        if self.spf_vs_spf:
            self.test_spf_filepath = self._kwargs.get('test_spf_filepath')
            self.reference_spf_filepath = self._kwargs.get('reference_spf_filepath')

        if self.oa_vs_spf:
            self.tech_opt = self._kwargs.get('tech_opt')
            self.flow = self._kwargs.get('flow')
            self.cds_lib = self._kwargs.get('cds_lib_filepath')
            self.kit = Kit.get(self.kit_name, self.tech_opt)
            self.library = 'intel'+str(self.kit.tech_id)+'prim'
            self.reference_spf_filepath = self._kwargs.get('reference_spf_filepath')

        self.out_dir = self.run_directory

    def run(self):
        """Method to run isotope based on
         input preferences"""
        isotope_flag = False
        try:
            if self.spf_vs_spf:
                isotope_flag = self.spf_isotope()
            elif self.oa_vs_spf:
                isotope_flag = self.oa_isotope()
            return isotope_flag
        except Exception as error:
            logging.exception("Exception at: %s", error)
            raise error

    def spf_isotope(self):
        """Run method for lpe_isotope"""
        try:
            summary_file = str(os.path.join(self.out_dir, "Results.summary"))
            with open(summary_file, 'a', encoding='utf8') as result_file:
                ins_flag = False
                isotope_flag = False
                if os.path.isfile(self.test_spf_filepath) and os.stat(self.test_spf_filepath).st_size != 0:
                    if os.path.isfile(self.reference_spf_filepath)\
                            and os.stat(self.reference_spf_filepath).st_size != 0:
                        skew_out_dir = os.path.join(self.out_dir, self.skew)
                        if not os.path.exists(skew_out_dir):
                            os.makedirs(skew_out_dir)
                        if self.compare_spf_instances(skew_out_dir):
                            ins_flag = True
                            res_str = "ISOTOPE : Pass\n"
                        else:
                            res_str = "ISOTOPE : Fail\n"
                    else:
                        logging.error("Reference file is empty/not found")
                        raise Exception("Reference file is empty/not found")
                else:
                    logging.error("Test file is not found/empty")
                    raise Exception("Test file is empty/not found")

                result_file.write(f'{self.skew}\nOLD SPF : {self.reference_spf_filepath}\n'
                                  f'NEW SPF : {self.test_spf_filepath}\n{res_str}\n\n')
            if self.lvs_tool_name == 'icv':
                isotope_flag = ins_flag and self.ped_pes_check()
            if self.lvs_tool_name == 'calibre':
                isotope_flag = ins_flag
            return isotope_flag

        except Exception as error:
            logging.exception("Exception at: %s", error)
            raise error

    @staticmethod
    def create_isotope_logger(log_file_name, log_dir):
        """Method to create log files for isotope"""

        formatter = logging.Formatter('%(levelname)s %(asctime)s %(message)s',
                                      datefmt="(%a %b %d %H:%M:%S %Y)")
        handler = logging.FileHandler(f'{log_dir}/{log_file_name}', mode='w')
        handler.setFormatter(formatter)
        logger = logging.getLogger(log_file_name)
        logger.setLevel(10)
        logger.addHandler(handler)

        return logger

    def compare_spf_instances(self, skew_out_dir) -> bool:
        """Args
        ---------
        output directory

        Returns
        --------
        Performs instance section comparison for the input files and returns True
        if they are 100% match"""

        try:

            comparison_logger = self.create_isotope_logger("comparison.log", skew_out_dir)
            comparison_logger.propagate = False
            parser_logger = self.create_isotope_logger("parser.log", skew_out_dir)

            parser_logger.info("Parsing DSPF %s", self.reference_spf_filepath)
            dev_data_ref = self.get_spf_instance_data(self.reference_spf_filepath)
            parser_logger.info("DONE")
            parser_logger.info("Parsing DSPF %s", self.test_spf_filepath)
            dev_data_cur = self.get_spf_instance_data(self.test_spf_filepath)
            parser_logger.info("DONE")

            parser_logger.info("%d instance(s) found in golden netlist and "
                               "%d instance(s) found in sample netlist",
                               len(dev_data_ref), len(dev_data_cur))

            if len(dev_data_ref) == len(dev_data_cur):
                rep_file = os.path.join(skew_out_dir, "propertymatch.rpt")
                with open(rep_file, 'w', encoding='utf8') as rep_file:
                    rep_file.write("LIST OF PARAMETERS IGNORED DURING COMPARISON:  ")
                    for item in self.exclude_list:
                        rep_file.write(item + ' ')
                    rep_file.write('\n# PROPERTY MATCH/MISMATCH TABLE:\n# ' + '=' * 140 + '\n')
                    rep_file.write(f"# {'NETLIST':22}{'DEVICE NAME':25}{'DEVICE MODEL':20}"
                                   f"{'MATCHED PROPERTIES':23}{'MISMATCHED PROPERTIES':21}\n")
                    rep_file.write('# ' + '=' * 140 + '\n''# ' + '=' * 140 + '\n')
                    comp_res = True
                    comparison_logger.log(0, "START COMPARISON")
                    for _, ref_dev in enumerate(dev_data_ref):
                        comparison_logger.info("Finding match for %s device in position %s %s %s"
                                               " in golden netlist", ref_dev.get("PROPERTY"),
                                               "x = " + ref_dev.get("x"), "y = " + ref_dev.get("y"),
                                               "angle = " + ref_dev.get("angle"))
                        for _, cur_dev in enumerate(dev_data_cur):
                            golden_replist = []
                            sample_replist = []
                            if ref_dev.get("x") == cur_dev.get("x") and \
                                    ref_dev.get("y") == cur_dev.get("y") and \
                                    ref_dev.get("angle") == cur_dev.get("angle"):
                                comparison_logger.info("Match found in sample netlist"
                                                       " with %s device", cur_dev.get("PROPERTY"))
                                comparison_logger.info("Comparing properties of %s in golden"
                                                       " netlist with %s in sample netlist",
                                                       ref_dev.get("PROPERTY"),
                                                       cur_dev.get("PROPERTY"))
                                rep_file.write(f"# {'MATCHED':<140}\n")
                                rep_file.write(f'# {"GOLDEN":<6}{ref_dev.get("PROPERTY"):>26}'
                                               f'{ref_dev.get("device_type"):>26}\n')
                                sample_replist.append(f"# {'SAMPLE':<6}{cur_dev.get('PROPERTY'):>26}"
                                                      f"{cur_dev.get('device_type'):>26}\n")
                                for param in ref_dev:
                                    if param != "PROPERTY" and param not in self.exclude_list:
                                        if ref_dev.get(param) == cur_dev.get(param):
                                            comparison_logger.info("Matched property %s",
                                                                   param + " = " + ref_dev.get(param))
                                            golden_replist. \
                                                append(f"# {param + ' = ' + ref_dev.get(param):>85}\n")
                                            sample_replist. \
                                                append(f"# {param + ' = ' + cur_dev.get(param):>85}\n")
                                        else:
                                            comp_res = False
                                            comparison_logger.info("Mismatched properties %s in"
                                                                   " golden netlist %s in sample"
                                                                   " netlist",
                                                                   param + " " + ref_dev.get(param),
                                                                   param + " = " + cur_dev.get(param))
                                            rep_file.write(f"# {'MISMATCHED':<140}\n")
                                            golden_replist. \
                                                append(f"# {param + ' = ' + ref_dev.get(param):>111}\n")
                                            sample_replist. \
                                                append(f"# {param + ' = ' + cur_dev.get(param):>111}\n")
                                for item in golden_replist:
                                    rep_file.write(item)
                                rep_file.write('# ' + '-' * 140 + '\n')
                                for item in sample_replist:
                                    rep_file.write(item)
                                rep_file.write(('# ' + ' ' * 140 + '\n') * 2)
                                rep_file.write('# ' + '=' * 140 + '\n')
            else:
                logging.info("Number of instances did not match for the files")
                comp_res = False
        except Exception as error:
            logging.exception(("Exception at: %s", error))
            raise error
        return comp_res

    def ped_pes_check(self) -> bool:
        """
        performs ped/pes values check for spf file generated in current run

        Returns
        --------
        True or False based on ped and pes values """

        if "ped" and "pes" in self.exclude_list:
            ped_pes_flag = True
            logging.info("ped_pes_check not performed as ped and pes are to be ignored")
        else:
            ins_sec_data = self.get_spf_instance_data(self.test_spf_filepath)
            try:
                ped_pes_flag = True
                for _, dev in enumerate(ins_sec_data):
                    if "ped" in dev:
                        if dev["ped"] == "0.001u" or dev["pes"] == "0.001u":
                            ped_pes_flag = False
            except Exception as error:
                logging.exception(("Exception at %s:", error))
                raise error
        return ped_pes_flag

    def generate_netlist_convert(self):
        """ Creates netlist convert file in rundir
        to run virtuoso tool and generate oa view file

        Returns:
        --------
        None
        """
        try:
            netlist_con = os.path.join(self.out_dir, 'netlist_convert')
            with open(netlist_con, 'w', encoding='UTF8') as netlist:
                logging.info("Generating netlist_convert file")
                if str(self.library).startswith("e"):
                    if self.kit.process == "1278":
                        dev_path = f'{self.kit.root}/libraries/prim/lnf/common/{self.library}'
                    else:
                        dev_path = f'{self.kit.root}/libraries/prim/lnf/{self.library}'

                    pattern = re.compile(r'[n/p][hp]')
                    dev_list = [dire for dire in os.listdir(dev_path) if
                                os.path.isdir(os.path.join(dev_path, dire))
                                and re.match(pattern, dire)]
                    netlist.write(f'envSetVal("asimenv.startup" '
                                  f'"projectDir" \'string "{self.out_dir}/simulation")\n')
                    counter = 0
                    for dev in dev_list:
                        if counter == 0:
                            netlist.write("foreach(cell list(")
                        netlist.write(f'"{dev}" ')
                        counter = counter + 1
                        if counter == 10:
                            netlist.write(f') cdfIdUser=cdfCreateUserCellCDF(ddGetObj('
                                          f'{self.library} cell))'
                                          f' cdfIdBase=cdfGetBaseCellCDF(ddGetObj("{self.library}"'
                                          f' cell)) cdfIdUser->simInfo '
                                          f'= list(nil spectre list(nil instParameters '
                                          f'append(cdfIdBase->simInfo->spectre->'
                                          f'instParameters \'(llx lly urx ury)))))\n')
                            counter = 0
                    if counter > 0:
                        netlist.write(f') cdfIdUser=cdfCreateUserCellCDF(ddGetObj'
                                      f'({self.library} cell)) cdfIdBase=cdfGetBaseCellCDF'
                                      f'(ddGetObj("{self.library}" cell)) cdfIdUser->'
                                      f'simInfo = list(nil spectre list(nil instParameters'
                                      f' append(cdfIdBase->simInfo->spectre->'
                                      f'instParameters \'(llx lly urx ury)))))\n')
                else:
                    if self.kit.process == "1278":
                        dev_path = f'{self.kit.root}/libraries' \
                                   f'/prim/pcell/common/{self.library}'
                    else:
                        dev_path = f'{self.kit.root}/libraries/prim/pcell/{self.library}'

                    pattern = re.compile(r'[n/p][hp]')
                    dev_list = [dire for dire in os.listdir(dev_path) if
                                os.path.isdir(os.path.join(dev_path, dire))
                                and re.match(pattern, dire)]

                    netlist.write(f'envSetVal("asimenv.startup" '
                                  f'"projectDir" \'string "{self.out_dir}/simulation")\n')
                    counter = 0
                    for dev in dev_list:
                        if counter == 0:
                            netlist.write("foreach(cell list(")
                        netlist.write(f'"{dev}" ')
                        counter = counter + 1
                        if counter == 10:
                            netlist.write(f') cdfIdUser=cdfCreateUserCellCDF'
                                          f'(ddGetObj("{self.library}" cell)) '
                                          f'cdfIdBase=cdfGetBaseCellCDF'
                                          f'(ddGetObj("{self.library}" cell)) '
                                          f'cdfIdUser->simInfo = cdfIdBase->simInfo '
                                          f'cdfIdUser->simInfo->spectre->instParameters = '
                                          f'append(cdfIdBase->simInfo->'
                                          f'spectre->instParameters \'(llx lly urx ury)))\n')
                            counter = 0
                    if counter > 0:
                        netlist.write(f') cdfIdUser=cdfCreateUserCellCDF'
                                      f'(ddGetObj("{self.library}" cell)) '
                                      f'cdfIdBase=cdfGetBaseCellCDF'
                                      f'(ddGetObj("{self.library}" cell)) '
                                      f'cdfIdUser->simInfo = cdfIdBase->simInfo '
                                      f'cdfIdUser->simInfo->spectre->instParameters = '
                                      f'append(cdfIdBase->simInfo->'
                                      f'spectre->instParameters \'(llx lly urx ury)))\n')
                netlist.write("simulator(\'spectre)\n")
                netlist.write(f'design("{getpass.getuser()}_p{self.kit.dot}" '
                              f'"{self.cell_name}" "{self.flow}.{self.skew}.{self.temperature}")\n')
                netlist.write("createNetlist()\n")
                netlist.write("exit()\n")
        except Exception as error:
            logging.exception("Error while running spectre netlist - %s", error)
            raise error

    def generate_oa(self):
        """
        Function to run Virtuoso tool with providing netlist_convert file
        as input
        Returns
        -------
        exit code and stdout
        """

        try:
            oa_lib = os.path.join(self.run_directory, f'{getpass.getuser()}_p{self.kit.dot}')
            if Path(os.path.join(self.extract_dir, 'oa_lib')).exists():
                shutil.copytree(os.path.join(self.extract_dir, 'oa_lib'), oa_lib)
            tool = Virtuoso(kit=self.kit,
                            cmd='virtuoso',
                            options=f'-nograph -replay {self.out_dir}/netlist_convert'
                                    f' -log {self.out_dir}/netlist_convert.log',
                            cds_lib=self.cds_lib,
                            component_type='pcell',
                            run_dir=self.out_dir)
            tool._cds_lib.add_libraries(lib_paths=[oa_lib])  # pylint: disable=protected-access
            tool._cds_lib.save(self.run_directory)  # pylint: disable=protected-access
            exitcode, stdout, _ = tool.run()
            logging.info("Running Virtuoso tool to generate oa file. Refer to netlist_convert.log")
            return exitcode, stdout
        except Exception as error:
            logging.exception("Error while running spectre netlist - %s", error)
            raise error

    def modify_scsfile(self, oa_file):
        """This Function creates a modified form of the oa file generated"""
        try:
            input_modified_scs = Path(f'{self.out_dir}/input_modified.scs')
            logging.info("modifying oa view file")
            with open(oa_file, 'r', encoding='utf8') as scs_file:
                with open(input_modified_scs, 'w', encoding='utf8') as input_modified_scs:
                    oa_lines = scs_file.readlines()
                    mod_lines = ''.join(oa_lines)
                    final_data = mod_lines.replace('\\\n', '')
                    input_modified_scs.write('\n' + final_data)
        except Exception as error:
            logging.exception("Exception at: %s", error)
            raise error

    def oa_isotope(self) -> bool:
        """Function to compare oa and spf files"""
        if not os.path.isfile(self.reference_spf_filepath):
            raise Exception("Test file is empty/not found")
        self.generate_netlist_convert()
        self.generate_oa()
        oa_file = Path(f'{self.out_dir}/simulation/{self.cell_name}'
                       f'/spectre/{self.flow}.{self.skew}.{self.temperature}/netlist/input.scs')
        if oa_file.is_file():
            self.modify_scsfile(oa_file)
            if self.compare_oa_spf_instances():
                logging.info("lpe_oa_isotope : Pass")
                oaspf_flag = True
            else:
                logging.error("lpe_oa_isotope : Fail")
                oaspf_flag = False
        else:
            oaspf_flag = False
            logging.error("OA netlist is not generated, refer to netlist_convert.log")
        return oaspf_flag

    def compare_oa_spf_instances(self) -> bool:
        """Args
        ---------
        spf file and oa file that needs to compared for devices
        and output directory to generate report file

        Returns
        --------
        Performs devices comparison for the input files and
        returns True if they are 100% match"""
        try:
            oa_file = Path(f'{self.out_dir}/input_modified.scs')
            dev_data_ref = self.get_spf_instance_data(self.reference_spf_filepath)
            dev_data_cur = self.get_oa_dev_data(oa_file)
            if len(dev_data_cur) == len(dev_data_ref):
                self.exclude_list.update(["si_w", "si_l", "x", "y", "angle", "PROPERTY"])
                rep_file = os.path.join(self.out_dir, "isotope_report.txt")
                logging.info("Generating report file...")
                with open(rep_file, 'w', encoding='utf8') as rep_file:
                    rep_file.write("ISOTOPE COMPARISON REPORT:\n\n")
                    rep_file.write("LIST OF PARAMETERS IGNORED DURING COMPARISON:")
                    for item in self.exclude_list:
                        rep_file.write(item + ' ')
                    rep_file.write("\n\nCOMPARISON DETAILS:\n\n")
                    comp_res = True
                    for _, ref_dev in enumerate(dev_data_ref):
                        for _, cur_dev in enumerate(dev_data_cur):
                            if ref_dev.get("llx") == cur_dev.get("llx") \
                                    and ref_dev.get("lly") == cur_dev.get("lly"):
                                rep_file.write(f"{'SPF INSTANCE':>63}{'OA INSTANCE':>50}\n")
                                rep_file.write(f'{"PROPERTY":51}{ref_dev.get("PROPERTY"):<51}'
                                               f'{cur_dev.get("PROPERTY"):<51}{"COMPARISON":<50}\n')
                                for param in ref_dev:
                                    if param not in self.exclude_list:
                                        if ref_dev.get(param) == cur_dev.get(param):
                                            rep_file.write(f'{param:51}{ref_dev.get(param):<51}'
                                                           f'{cur_dev.get(param):<51}{"MATCH":<51}\n')
                                        else:
                                            rep_file.write(
                                                f'{param:51}{ref_dev.get(param):<51}'
                                                f'{cur_dev.get(param):<51}{"MISMATCH":<51}\n')
                                            comp_res = False
                                rep_file.write('-' * 160 + '\n')
                logging.info("Comparison completed, refer to report file in output directory")
            else:
                logging.info("Number of instances did not match for the files")
                comp_res = False
        except Exception as error:
            logging.exception("Exception at: %s", error)
            raise error
        return comp_res

    @staticmethod
    def org_instance_data(ins_list: list) -> list:
        """
        Args
        -----
        list of lines where each line has device data collected from spf/oa view files
        Returns
        -------
        list of dictionaries where each dict has properties and values from device data
        """
        try:
            if ins_list:
                ins_data = []
                for dev_line in ins_list:
                    dev_line = dev_line.split()
                    if len(dev_line) > 2:
                        dev_prop = dev_line.copy()
                        for prop in dev_line:
                            if "=" in prop:
                                counter = dev_line.index(prop)
                                del dev_prop[0:counter]
                                dev_prop.insert(0, "PROPERTY=" + dev_line[0])
                                dev_prop.insert(1, "device_type=" + dev_line[counter - 1])
                                dev_prop.insert(2, "num_of_ports=" + str(counter - 2))
                                break
                        dev_data = {}
                        for val in dev_prop:
                            if val:
                                tmp = val.split("=", 1)
                                dev_data[tmp[0]] = tmp[1]
                        ins_data.append(dev_data)
            else:
                raise Exception("instance section lines are not collected from spf file")
            assert len(ins_data) != 0
            logging.info("Device data is ready for comparison")
            return ins_data
        except Exception as error:
            logging.exception("Exception at: %s", error)
            raise error

    def get_spf_instance_data(self, spf_file) -> list:
        """
        Args
        -----
        spf file

        Returns
        -------
        This method returns data from instance section of the input file in the form of a list.
        Each list item contains lines instance section from input spf file
        """

        try:
            ins_list = []
            ins_data = []
            flag_ins = False
            with open(spf_file, "r", encoding='utf8') as file:
                for line in file:
                    if "Instance Section" in line:
                        flag_ins = True
                        continue
                    if flag_ins:
                        ins_list.append(line.strip("\n"))
            if flag_ins:
                ins_data = self.org_instance_data(ins_list)
                logging.info("Device data is found in input spf file")
            return ins_data

        except Exception as error:
            logging.exception("Exception at: %s", error)
            raise error

    def get_oa_dev_data(self, oa_file) -> list:
        """
        Args
        -----
       spf file

        Returns
        -------
        This method returns data from instance section of the input file in the
        form of a list. Each list item contains lines of device data from input scs file
       """

        try:
            ins_lines = []
            dev_data = []
            flag_ins = False
            with open(oa_file, "r", encoding='utf8') as file:
                for line in file:
                    if "llx" in line or "djnw" in line:
                        ins_lines.append(line.strip("\n"))
                        flag_ins = True
            if flag_ins:
                dev_data = self.org_instance_data(ins_lines)
                logging.info("Device data found in input oa file")
            return dev_data

        except Exception as error:
            logging.exception("Exception at: %s", error)
            raise error
