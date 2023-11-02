"""This file performs the compare rc  flow"""
import logging

from waldo.model import Kit
from waldo.tool.starrcxt.compare_parasitics import CompareParasitics


class LpeCompareRC:
    """This class used compare_rc flow"""

    def __init__(self, **kwargs: dict) -> None:
        """Create CompareParasitics tool object.

                Parameters:
                -----------
                kwargs : dict
                    input dictionary.
                kit_name : str
                    kit name to create kit object.
                tech_opt : str
                    technology option of kit to create kit object
                """

        self.kwargs = kwargs
        self.kit_name = self.kwargs.get('kit_name')
        self.tech_opt = self.kwargs.get('tech_opt')
        self.kit = Kit.get(self.kit_name, self.tech_opt)

    def compare_rc(self) -> tuple:
        """Using CompareParasitics tool for rc comparison

            Parameters:
            -----------

            run_directory: str
                To check run_directory is available or not if not to create.
            kit : Kit
                Kit object.
            test_rc_file : str
                RC file to check.
            reference_rc_file : str
                Golden RC file to check against.

           Returns:
           --------

           Tuple[int, str, str]
               Tuple of (rptgen_returncode, standard output string, standard error string)
               returns by run method. In this run method .rpt files will generate.

               Tuple of (reggen_returncode, standard output string, standard error string)
               returns by plot method. In this plot method .regression files will generate.
           tcap : str
               Pass if meet certification criteria otherwise fail.
           ccap : str
               Pass if meet certification criteria otherwise fail.
           p2p : str
               Pass if meet certification criteria otherwise fail.
           Raises:
           -------
           TypeError:
               Raised if kit object not created.
           FileNotFoundError:
               Raised if test_rc_file/reference_rc_file not available.
           FileNotFoundError:
               Raised if compare_parasitics.log is not available in given run_directory.

           """

        try:
            compare_rc_settings = {
                'kit': self.kit,
                'run_dir': self.kwargs.get('run_directory'),
                'reference_rc_file': self.kwargs.get('reference_spf_filepath'),
                'test_rc_file': self.kwargs.get('test_spf_filepath'),
            }
            compare_rc = CompareParasitics(**compare_rc_settings)
            logging.info("Using CompareParasitics tool for rc comparison")
            logging.info(".rpt file are generating....")
            rptgen_returncode, _, _ = compare_rc.run()
            logging.info("Successfully .rpt files are generated")
            logging.info("Regression files are generating....")
            reggen_returncode, _, _ = compare_rc.plot(self.kit.process)
            logging.info("Successfully regression files are generated")
            logging.info("Checking total capacitance, coupling capacitance "
                         "and pin-pin resistance "
                         "against the given certification criteria....")
            logging.info("And updating the status of capacitance, coupling "
                         "capacitance and pin-pin "
                         "resistance either fail or pass....")
            compare_rc.correlate()
            tcap = compare_rc.tcap_status
            logging.info("Total capacitance status: pass")
            ccap = compare_rc.ccap_status
            logging.info("Coupling capacitance status: pass")
            p2p = compare_rc.p2p_res_status
            logging.info("Pin-Pin resistance status: pass")
            return rptgen_returncode, reggen_returncode, tcap, ccap, p2p
        except Exception as error:
            logging.exception("Exception at CompareParasitics tool: %s", error)
            raise error
