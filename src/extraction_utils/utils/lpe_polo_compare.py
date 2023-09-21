""" Module to compare the post and prelayout simulation """

import logging
import re
from pathlib import Path

class LpePoloCompare():
    """ Compare simulation results """

    def __init__(self, **kwargs: dict):
        """ Run polo comparison for new and old files

        parameters
        ------
        new_polo_file: str, Required
            Path to POLO file from new release
        old_polo_file: str, Required
            Path to POLO file from old release
        run_dir: str, Required
            run directory file with respect to the different skews


        Keyword Arguments
        -----------------
        -compare_new: bool
            Compare pre-layout result vs POLO result in new file
        -compare_old: bool, Optional
            Compare pre-layout result vs POLO result in old file
        -compare_newvsold_polo: bool, Optional
            Compare new release POLO result vs  old release POLO result
        -compare_newvsold_prelpayout: bool, Optional
            Compare new release prelayout result vs old release prelayout result
        -pct_error: int, Required
            Eror limit in percent

        Returns: None
        ------------
        """
        self._kwargs = kwargs
        self.kit_name = self._kwargs.get('kit_name')
        self.cell_name = self._kwargs.get('cell_name')
        self.new_polo_file = self._kwargs.get('new_polo_file')
        self.old_polo_file = self._kwargs.get('old_polo_file')
        self.run_dir = self._kwargs.get('run_directory')
        self.pct_error = self._kwargs.get('pct_error')
        self.compare_new = self._kwargs.get('compare_new')
        self.compare_old = self._kwargs.get('compare_old')
        self.compare_newvsold_prelayout = self._kwargs.get('compare_newvsold_prelayout')
        self.compare_newvsold_polo = self._kwargs.get('compare_newvsold_polo')
        self.extraction_view = self._kwargs.get('extraction_view')

        if self.new_polo_file and self.old_polo_file:
            if not Path(self.new_polo_file).exists():
                logging.error("Error: new file  %s not found\n", self.new_polo_file)
                raise FileNotFoundError(f"Error: new file {self.new_polo_file} not found\n")
            if not Path(self.old_polo_file).exists():
                logging.error("Error: old file %s not found\n", self.old_polo_file)
                raise FileNotFoundError(f"Error: old file {self.old_polo_file} not found\n")

    def run_compare(self):
        """ Run polo comparison for new and old files

        parameters
        ------
        new_polo_file: str, Required
            Path to POLO file from new release
        old_polo_file: str, Required
            Path to POLO file from old release
        run_dir: str, Required
            Output file with respect to the different skews
            Ex: ttt/Result.polocompare

        Keyword Arguments
        -----------------
        -compare_new: bool
            Compare pre-layout result vs POLO result in new file
        -compare_old: bool, Optional
            Compare pre-layout result vs POLO result in old file
        -compare_newvsold_polo: bool, Optional
            Compare new release POLO result vs  old release POLO result
        -compare_newvsold_prelpayout: bool, Optional
            Compare new release prelayout result vs old release prelayout result
        -pct_error: int, Required
            Eror limit in percent

        Returns: None
        ------------
        """

        return_code =  []
        if self.extraction_view in ('oa','smc-oa'):
            (new_prelay_name, new_prelay_value, new_polo_name, new_polo_value) = \
                self.parse_oa_polofile(self.new_polo_file,self.extraction_view)
            (old_prelay_name, old_prelay_value, old_polo_name, old_polo_value) = \
                self.parse_oa_polofile(self.old_polo_file, self.extraction_view)
        else:
            (new_prelay_name, new_prelay_value, new_polo_name, new_polo_value) = self.parse_polofile(self.new_polo_file)
            (old_prelay_name, old_prelay_value, old_polo_name, old_polo_value) = self.parse_polofile(self.old_polo_file)

        out_file = str(Path(self.run_dir)/'Result.polocompare')
        with open(Path(out_file), 'w', encoding='utf8') as res_file:
            if self.compare_new:
                logging.info("Compare pre-layout result vs POLO result in new file")
                logging.info("Wrting the results in %s", out_file)
                (returnrc_new, return_diff) = self.compare_name_and_value(self.pct_error,
                    new_prelay_name, new_prelay_value, new_polo_name, new_polo_value)
                return_code.append(returnrc_new)
                res_file.write(f"New File {self.new_polo_file}\n")
                if returnrc_new == 0:
                    res_file.write("Name and value match for Prelayout vs Polo for the new run\n")
                    res_file.write(f"    Prelay: {new_prelay_name} = {new_prelay_value}\n")
                    res_file.write(f"    POLO:   {new_polo_name} = {new_polo_value}\n\n")
                elif returnrc_new == 1:
                    res_file.write(f"Values do not match within {self.pct_error}% "+
                            "for Prelayout vs Polo for the new run\n")
                    res_file.write(f"    Prelay: {new_prelay_name} = {new_prelay_value}\n")
                    res_file.write(f"    POLO:   {new_polo_name} = {new_polo_value}\n")
                    res_file.write(f"    Difference: {return_diff}%\n\n")
                elif returnrc_new == 2:
                    res_file.write("Names do not match for Prelayout vs Polo for the new run\n")
                    res_file.write(f"    Prelay: {new_prelay_name} = {new_prelay_value}\n")
                    res_file.write(f"    POLO:   {new_polo_name} = {new_polo_value}\n\n")

            # comparing old run values
            if self.compare_old:
                (returnrc_old, return_diff) = self.compare_name_and_value(self.pct_error,
                        old_prelay_name, old_prelay_value, old_polo_name, old_polo_value)
                return_code.append(returnrc_old)
                logging.info("Compare pre-layout result vs POLO result in old file")
                logging.info("Wrting the results in %s", out_file)
                res_file.write(f"Old File {self.old_polo_file}\n")
                if returnrc_old == 0:
                    res_file.write("Name and value match for Prelayout vs Polo for the old run\n")
                    res_file.write(f"    Prelay: {old_prelay_name} = {old_prelay_value}\n")
                    res_file.write(f"    POLO:   {old_polo_name} = {old_polo_value}\n\n")
                elif returnrc_old == 1:
                    res_file.write(f"Values do not match within {self.pct_error}% " +
                                "for Prelayout vs Polo for the old run\n")
                    res_file.write(f"    Prelay: {old_prelay_name} = {old_prelay_value}\n")
                    res_file.write(f"    POLO:   {old_polo_name} = {old_polo_value}\n")
                    res_file.write(f"    Difference: {return_diff}%\n\n")
                elif returnrc_old == 2:
                    res_file.write("Names do not match for Prelayout vs Polo for the old run\n")
                    res_file.write(f"    Prelay: {old_prelay_name} = {old_prelay_value}\n")
                    res_file.write(f"    POLO:   {old_polo_name} = {old_polo_value}\n\n")

            #compare the values of new and old polo simulation
            if self.compare_newvsold_polo:
                returnrc_newvsold_polo, return_diff = self.compare_name_and_value(self.pct_error,
                    new_polo_name, new_polo_value, old_polo_name, old_polo_value)
                return_code.append(returnrc_newvsold_polo)
                logging.info("Compare new release POLO result vs  old release POLO result")
                logging.info("Wrting the results in %s", out_file)
                res_file.write(f"New File {self.new_polo_file}\n")
                res_file.write(f"Old File {self.old_polo_file}\n")
                if returnrc_newvsold_polo == 0:
                    res_file.write("Name and value match for New Run Polo vs Old Run Polo\n")
                    res_file.write(f"    New POLO: {new_polo_name} = {new_polo_value}\n")
                    res_file.write(f"    OLD POLO: {old_polo_name} = {old_polo_value}\n\n")
                elif returnrc_newvsold_polo == 1:
                    res_file.write(f"Values do not match within {self.pct_error}% "+
                        "for New Run Polo vs Old Run Polo\n")
                    res_file.write(f"    New POLO: {new_polo_name} = {new_polo_value}\n")
                    res_file.write(f"    OLD POLO: {old_polo_name} = {old_polo_value}\n")
                    res_file.write(f"    Difference: {return_diff}%\n\n")
                elif returnrc_newvsold_polo == 2:
                    res_file.write("Names do not match for Polo vs Polo for the new and old run\n")
                    res_file.write(f"    New POLO: {new_polo_name} = {new_polo_value}\n")
                    res_file.write(f"    OLD POLO: {old_polo_name} = {old_polo_value}\n\n")

            #comparing the new and old prelayout simulation
            if self.compare_newvsold_prelayout:
                returnrc_newvsold_prelayout, return_diff = self.compare_name_and_value(
                    self.pct_error,new_prelay_name, new_prelay_value,
                    old_prelay_name, old_prelay_value)
                return_code.append(returnrc_newvsold_prelayout)
                logging.info("Compare new release prelayout result vs old release prelayout result")
                logging.info("Wrting the results in %s", out_file)
                res_file.write(f"New File {self.new_polo_file}\n")
                res_file.write(f"Old File {self.old_polo_file}\n")
                if returnrc_newvsold_prelayout == 0:
                    res_file.write("Name and value match for New Run Prelayout vs Old Run Prelayout\n")
                    res_file.write(f"    New Prelayout: {new_prelay_name} = {new_prelay_value}\n")
                    res_file.write(f"    OLD Prelayout: {old_prelay_name} = {old_prelay_value}\n\n")
                elif returnrc_newvsold_prelayout == 1:
                    res_file.write(f"Values do not match within {self.pct_error}% "+
                        "for New Run Prelayout vs Old Run Prelayout\n")
                    res_file.write(f"    New Prelayout: {new_prelay_name} = {new_prelay_value}\n")
                    res_file.write(f"    OLD Prelayout: {old_prelay_name} = {old_prelay_value}\n")
                    res_file.write(f"    Difference: {return_diff}%\n\n")
                elif returnrc_newvsold_prelayout == 2:
                    res_file.write("Names do not match for Prelayout vs Prelayout for the new and old run\n")
                    res_file.write(f"    New Prelayout: {new_prelay_name} = {new_prelay_value}\n")
                    res_file.write(f"    OLD Prelayout: {old_prelay_name} = {old_prelay_value}\n\n")

        #check for the difference in comparision
        if all(x == 0 for x in return_code):
            logging.info('Polo compare passed ')
            return 0
        logging.info('Polo compare Failed')
        return 1

    @staticmethod
    def parse_polofile(file) -> tuple:
        """ This method parse the file data
        parameters
        ----------
        file: str, Required
            polo .out file to parse the values.

        returns
        -------
        prelay_name: str,
            prelay name
        prely_value : float,
            value of pre layout simulation run
        polo_prelay: str,
            post layout name
        polo_value: float,
            value of post layout simulation run
        """
        prelay_name = prelay_value = polo_name = polo_value = None
        try:
            logging.info("Reading the file %s", file)
            with open(file, 'r', encoding='utf8') as sim_file:
                for line in sim_file.readlines():
                    if re.search(r'\(prelay\)\s*([\w_]*)=([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)', line):
                        match = re.search(r'\(prelay\)\s*([\w_]*)=([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)', line)
                        prelay = match.group(0).replace('=',' ').split(' ')
                        prelay_name = prelay[2]
                        prelay_value = prelay[3]
                    if re.search(r'\(polo\)\s*([\w_]*)=([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)', line):
                        match = re.search(r'\(polo\)\s*([\w_]*)=([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)', line)
                        polo = match.group(0).replace('=',' ').split(' ')
                        polo_name = polo[2]
                        polo_value = polo[3]
        except FileNotFoundError as error:
            logging.exception("Error: cannot open %s for read", error)
            raise FileNotFoundError(f'Error: Cannot open {file} for read') from error

        return(prelay_name, prelay_value, polo_name, polo_value)

    @staticmethod
    def parse_oa_polofile(file,extraction_view) -> tuple:
        """ This method parse the file data
        parameters
        ----------
        file: str, Required
            polo oa .out file to parse the values.
        """
        prelay_name = prelay_value = polo_name = polo_value = None
        try:
            logging.info("Reading the file %s", file)
            with open(file, 'r', encoding='utf8') as sim_file:
                for line in sim_file.readlines():
                    if re.search(r'\(prelay\)\s*([\w_]*)=([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)', line):
                        match = re.search(r'\(prelay\)\s*([\w_]*)=([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)', line)
                        prelay = match.group(0).replace('=',' ').split(' ')
                        prelay_name = prelay[2]
                        prelay_value = prelay[3]
                    if extraction_view in ('oa', 'smc-oa'):
                        if re.search(r'\('+extraction_view+'\)\s*([\w_]*)=([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)', line):
                            match = re.search(r'\('+extraction_view+'\)\s*([\w_]*)=([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)', line)
                            polo = match.group(0).replace('=',' ').split(' ')
                            polo_name = polo[2]
                            polo_value = polo[3]
        except FileNotFoundError as error:
            logging.exception("Error: cannot open %s for read", error)
            raise FileNotFoundError(f'Error: Cannot open {file} for read') from error

        return(prelay_name, prelay_value, polo_name, polo_value)

    @staticmethod
    def compare_name_and_value(pct_error, new_name, new_value, old_name, old_value) -> tuple:
        """ This method compares the simulation values

        parameters:
        ----------
        pct_error: int, Required
            Error limit value in percentage
        new_name: str, Required
            Name of the new run value (eg, freq)
        new_value: float, required
            new run value
        old_name: str, Required
            Name of the  old run value (eg, freq)
        old_value: float, required
            old run value
        """
        diff = 0
        if not re.match(old_name, new_name):
            return (2, 0)
        diff = 100 * (float(old_value) - float(new_value)) / float(old_value)
        if -pct_error <= diff <= pct_error:
            return(0, diff)

        return(1, diff)
