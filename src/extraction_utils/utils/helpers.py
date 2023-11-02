"""Helpers has the common methods used by most of the test patterns"""
import logging
from waldo.model import Kit


class Helpers:
    """Start of Helpers class which has various methods for validating parameters"""

    def __init__(self, **kwargs):
        """Initialize Helpers object

        Keyword Arguments
        -----------------
        kit_name : str
            Kit name
        tech_opt : str
            Tech opt for kit, can be ''
        lib_name : str
            Library name
        cell_name :
            Cell name from kit
        run_directory : str
            Path to the directory to run extraction in
        skew : str
            Skew
        temperature : str
            Temperature
        cds_lib_filepath : str
            file path for cds include library
        writeoa_output : bool
            True to write OA view output
        si_run_dir : str
            si run directory to generate oa view, by default run directory path
        output_netlist_format : str
            spf for generating spf file, '' in case of writing OA view, spef for spef file as output
        lvs_tool_name : str
            icv, calibre, pvs, pegasus options are accepted
        waiveoff_lvs_errors : bool
            True for waiving off any layout/lvs errors from kit, otherwise False
        layout_filetype : str
            'oa', 'gds' depending upon requirement
        schematic_filetype : str
            'oa', 'sp' depending upon requirement
        gds_filepath : str
            path of gds layout file type else ''
        sp_filepath : str
            path of spice netlist file type i.e. sp schematic file type else ''
        ndm_dbpath : str
            ndm database path else ''
        def_filepath : str
            def file path else ''
        annotated_gds_output : bool
            True for generating annotated gds output else False
        extract_tool : str
            extraction tool to be used, accepts starrc, qrc
        si_optional_settings : dict
            kwargs for si module like lnf_component, netlist_file_name, simulator, environment
        oasisout_optional_settings : dict
            kwargs for oasisout module like lnf_component, log_file, etc.
        lvs_optional_settings : dict
            kwargs for lvs module like command_line_args, extraction, etc.
        extract_optional_settings : dict
            kwargs for extract module like gds_map, layermap, etc.

        """
        self.netlist_format_types = ('', 'spf', 'spef')
        self.extraction_tools = ('starrc', 'qrc')
        self.lvs_tools = ('icv', 'calibre', 'pvs', 'pegasus')
        self.kwargs = kwargs
        self.kit_name = self.kwargs.get('kit_name')
        self.tech_opt = self.kwargs.get('tech_opt')
        self.kit = Kit.get(self.kit_name, self.tech_opt)
        self.lib_name = self.kwargs.get('lib_name')
        self.cell_name = self.kwargs.get('cell_name')
        self.temperature = self.kwargs.get('temperature')
        self.skew = self.kwargs.get('skew')
        self.run_dir = self.kwargs.get('run_directory')
        self.lvs_tool_name = self.kwargs.get('lvs_tool_name')

    def validate_extraction_parameters(self) -> dict:
        """Method to validate yaml parameters for extraction

        Returns:
        --------
        util_inputs : dict
            Returns dictionary having validated parameters for util lpe_extract

        Raises:
        -------
        Exception:
            This raises if any invalid parameter.

        """
        native_star = self.kwargs.get('native_star')
        write_oa = self.kwargs.get('writeoa_output')
        si_run_dir = self.kwargs.get('si_run_dir')
        netlist_format = self.kwargs.get('output_netlist_format')
        if netlist_format not in self.netlist_format_types:
            raise Exception("Incorrect netlist format")

        waiveoff_lvs_errors = self.kwargs.get('waiveoff_lvs_errors')
        schematic_filepath = self.kwargs.get('schematic_filepath')
        layout_filepath = self.kwargs.get('layout_filepath')
        ndm_dbpath = self.kwargs.get('ndm_dbpath')
        def_filepath = self.kwargs.get('def_filepath')
        agds_flag = self.kwargs.get('annotated_gds_output')
        extract_tool = self.kwargs.get('extract_tool')
        rcx_lvs_flag = self.kwargs.get('rcx_lvs')
        if extract_tool.lower() not in self.extraction_tools:
            raise Exception("This extract tool is not supported")
        cds_lib = self.kwargs.get('cds_lib_filepath')
        netlist_file = ''
        layout_file = ''

        if ndm_dbpath or def_filepath:
            layout_filepath = schematic_filepath = schematic_filetype = layout_filetype = self.lvs_tool_name \
                = None

        if ndm_dbpath and extract_tool.lower() != 'starrc':
            logging.error("ndm path should be given to starrc tool only")
            raise Exception("ndm path should be given to starrc tool only")

        if not (ndm_dbpath or def_filepath):
            self.validate_lvs_tool_name()

        si_optional_settings = self.kwargs.get('si_optional_settings')
        extract_optional_settings = self.kwargs.get('extract_optional_settings')
        oasisout_optional_settings = self.kwargs.get('oasisout_optional_settings')
        lvs_optional_settings = self.kwargs.get('lvs_optional_settings')
        si_settings = {
            'kit': self.kit,
            'lib_name': self.lib_name,
            'cell_name': self.cell_name,
            'run_dir': self.run_dir,
            'cds_lib': cds_lib
        }

        if si_optional_settings:
            si_settings.update(si_optional_settings)

        oasis_out_settings = {
            "kit": self.kit,
            "lib_name": self.lib_name,
            "cell_name": self.cell_name,
            "run_dir": self.run_dir,
            "cds_lib": cds_lib,
            "enable_coloring": True
        }
        if oasisout_optional_settings:
            oasis_out_settings.update(oasisout_optional_settings)

        icv_lvs_defines = {
            "_drCaseSensitive": "1",
            "_drIncludePort": True,
            "_drRenameAllSyn": True,
            "GATEDIR_VERT": "1",
            "_drRCextract": rcx_lvs_flag,
            "_drICFOAlayers": True,
            "_drEXTRACT_DJNW": True,
            "_drFILTER_DJNW": True,
            "_drRCextractAnnotate": True,
            "_ICV_PEX_SWAP_PROP": True,
            "_drIgnorePODEdiffcap": True,
            "_drNativeExtract": True
        }
        lvs_settings = {
            'kit': self.kit,
            'cell_name': self.cell_name,
            'layout': layout_filepath,
            'netlist': schematic_filepath,
            'run_dir': self.run_dir,
            'defines': icv_lvs_defines if self.lvs_tool_name == 'icv' else None,
        }
        if lvs_optional_settings:
            lvs_settings.update(lvs_optional_settings)

        extract_settings = {
            'kit': self.kit,
            'block_name': self.cell_name,
            'run_dir': self.run_dir,
            'skew': self.skew,
            'temperature': self.temperature,
            'native_star': native_star,
            'ndm': ndm_dbpath if ndm_dbpath else None,
            'def_file': def_filepath if def_filepath else None,
            'netlist': schematic_filepath,
            'lvs_tool_name': self.lvs_tool_name,
            'lvs_run_dir': self.run_dir,
        }
        if extract_optional_settings:
            extract_settings.update(extract_optional_settings)

        if netlist_format != '':
            extract_settings.update({'netlist_format': netlist_format})

        if not ndm_dbpath or def_filepath:
            if self.lvs_tool_name == 'icv':
                lvs_settings.update({'agds': agds_flag})
            if write_oa and si_run_dir == '':
                logging.info('si run dir path is missing for writing oa output hence writing to '
                             'run directory')
                si_run_dir = self.run_dir
            extract_settings.update({'write_oa': write_oa, 'si_run_dir': si_run_dir})
        util_inputs = {'run_dir': self.run_dir, 'cell_name': self.cell_name,
                       'si_settings': si_settings, 'oasis_out_settings': oasis_out_settings,
                       'lvs_settings': lvs_settings, 'extract_settings': extract_settings,
                       'waiveoff_lvs_errors': waiveoff_lvs_errors, 'ndm_dbpath': ndm_dbpath,
                       'layout_filepath': layout_filepath, 'schematic_filepath': schematic_filepath,
                       'def_filepath': def_filepath, 'lvs_tool_name': self.lvs_tool_name,
                       'extract_tool': extract_tool, 'write_oa': write_oa}
        return util_inputs

    def validate_lvs_tool_name(self):
        """Method to check if user has given proper lvs tool name"""

        if self.lvs_tool_name not in self.lvs_tools:
            raise Exception("lvs tool not supported or lvs tool attribute is empty")
