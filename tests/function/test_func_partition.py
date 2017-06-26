#!/usr/bin/env python
# Copyright 2017 IBM Corp. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Function tests for the 'zhmc_partition' Ansible module.
"""

import pytest
import mock

from ansible.modules.zhmc import zhmc_partition
from zhmcclient import Client
from zhmcclient_mock import FakedSession
from .func_utils import mock_ansible_module

# FakedSession() init arguments
FAKED_SESSION_KWARGS = dict(
    host='fake-host',
    hmc_name='faked-hmc-name',
    hmc_version='2.13.1',
    api_version='1.8'
)

# Faked CPC in DPM mode that is used for all tests
# (with property names as specified in HMC data model)
FAKED_CPC_1 = {
    'object-id': 'cpc-oid-1',
    # object-uri is auto-generated
    'class': 'cpc',
    'name': 'cpc-name-1',
    'description': 'CPC #1 in DPM mode',
    'status': 'active',
    'dpm-enabled': True,
    'is-ensemble-member': False,
    'iml-mode': 'dpm',
}

# Faked partition that is used for these tests. Most properties are set to
# their default values. Note, we are prepping a faked partition; we are not
# passing these properties to PartitionManager.create().
FAKED_PARTITION_1_NAME = 'part-name-1'
FAKED_PARTITION_1 = {
    # object-id is auto-generated
    # object-uri is auto-generated
    'parent': '/api/cpcs/cpc-name-1',
    'class': 'partition',
    'name': FAKED_PARTITION_1_NAME,
    'description': 'Partition #1',
    'short-name': 'PART1',
    'partition-id': '4F',
    'ifl-processors': 1,
    'initial-memory': 1024,
    'maximum-memory': 2048,
    'status': 'stopped',
    'acceptable-status': ['active', 'stopped'],
    'has-unacceptable-status': False,

    # The remaining properties get their default values:
    'is-locked': False,
    'type': 'linux',
    'autogenerate-partition-id': True,
    'os-name': '',
    'os-type': '',
    'os-version': '',
    'reserve-resources': False,
    'degraded-adapters': [],
    'processor-mode': 'shared',
    'cp-processors': 0,
    'ifl-absolute-processor-capping': False,
    'cp-absolute-processor-capping': False,
    'ifl-absolute-processor-capping-value': 1.0,
    'cp-absolute-processor-capping-value': 1.0,
    'ifl-processing-weight-capped': False,
    'cp-processing-weight-capped': False,
    'minimum-ifl-processing-weight': 1,
    'minimum-cp-processing-weight': 1,
    'initial-ifl-processing-weight': 100,
    'initial-cp-processing-weight': 100,
    'current-ifl-processing-weight': 42,
    'current-cp-processing-weight': 100,
    'maximum-ifl-processing-weight': 999,
    'maximum-cp-processing-weight': 999,
    'processor-management-enabled': False,
    'reserved-memory': 1024,
    'auto-start': False,
    'boot-device': 'none',
    'boot-network-device': None,
    'boot-ftp-host': None,
    'boot-ftp-username': None,
    'boot-ftp-password': None,
    'boot-ftp-insfile': None,
    'boot-removable-media': None,
    'boot-removable-media-type': None,
    'boot-timeout': 60,
    'boot-storage-device': None,
    'boot-logical-unit-number': '',
    'boot-world-wide-port-name': '',
    'boot-configuration-selector': 0,
    'boot-record-lba': None,
    'boot-os-specific-parameters': None,
    'boot-iso-image-name': None,
    'boot-iso-ins-file': None,
    'access-global-performance-data': False,
    'permit-cross-partition-commands': False,
    'access-basic-counter-set': False,
    'access-problem-state-counter-set': False,
    'access-crypto-activity-counter-set': False,
    'access-extended-counter-set': False,
    'access-coprocessor-group-set': False,
    'access-basic-sampling': False,
    'access-diagnostic-sampling': False,
    'permit-des-key-import-functions': True,
    'permit-aes-key-import-functions': True,
    'threads-per-processor': 0,
    'virtual-function-uris': [],
    'nic-uris': [],
    'hba-uris': [],
    'crypto-configuration': None,

    # SSC-only properties; they are not present for type='linux'
    # 'ssc-host-name': None,
    # 'ssc-boot-selection': None,
    # 'ssc-ipv4-gateway': None,
    # 'ssc-dns-servers': None,
    # 'ssc-master-userid': None,
    # 'ssc-master-pw': None,
}

# Faked HBA that is used for these tests (for partition boot from storage).
# Most properties are set to their default values.
FAKED_HBA_1_NAME = 'hba-1'
FAKED_HBA_1 = {
    # element-id is auto-generated
    # element-uri is auto-generated
    'parent': '/api/partitions/{}'.format(FAKED_PARTITION_1_NAME),
    'class': 'hba',
    'name': FAKED_HBA_1_NAME,
    'description': 'HBA #1',
    'device_number': '012F',
    'wwpn': 'abcdef0123456789',
    'adapter-port-uri': 'faked-adapter-port-uri',
}

# Faked OSA NIC that is used for these tests (for partition boot from storage).
# Most properties are set to their default values.
FAKED_NIC_1_NAME = 'nic-1'
FAKED_NIC_1 = {
    # element-id is auto-generated
    # element-uri is auto-generated
    'parent': '/api/partitions/{}'.format(FAKED_PARTITION_1_NAME),
    'class': 'nic',
    'name': FAKED_NIC_1_NAME,
    'description': 'NIC #1',
    'device_number': '022F',
    'virtual-switch-uri': 'faked-vswitch-uri',
    'type': 'osd',
    'ssc-management-nic': False,
    'mac-address': 'fa:ce:da:dd:6e:55',
}

# Translation table from 'state' module input parameter to corresponding
# desired partition 'status' property value. 'None' means the partition
# does not exist.
PARTITION_STATUS_FROM_STATE = {
    'absent': None,
    'stopped': 'stopped',
    'active': 'active',
}


def get_failure_msg(mod_obj):
    """
    Return the module failure message, as a string (i.e. the 'msg' argument
    of the call to fail_json()).
    If the module succeeded, return None.
    """

    def func(msg):
        return msg

    if not mod_obj.fail_json.called:
        return None
    call_args = mod_obj.fail_json.call_args

    # The following makes sure we get the arguments regardless of whether they
    # were specified as positional or keyword arguments:
    return func(*call_args[0], **call_args[1])


def get_module_output(mod_obj):
    """
    Return the module output as a tuple (changed, partition_properties) (i.e.
    the arguments of the call to exit_json()).
    If the module failed, return None.
    """

    def func(changed, partition):
        return changed, partition

    if not mod_obj.exit_json.called:
        return None
    call_args = mod_obj.exit_json.call_args

    # The following makes sure we get the arguments regardless of whether they
    # were specified as positional or keyword arguments:
    return func(*call_args[0], **call_args[1])


class TestPartition(object):
    """
    All tests for partitions.
    """

    def setup_method(self):
        """
        Using the zhmcclient mock support, set up a CPC in DPM mode, that has
        no partitions.
        """
        self.session = FakedSession(**FAKED_SESSION_KWARGS)
        self.client = Client(self.session)
        self.faked_cpc = self.session.hmc.cpcs.add(FAKED_CPC_1)
        cpcs = self.client.cpcs.list()
        assert len(cpcs) == 1
        self.cpc = cpcs[0]

    def setup_partition(self, initial_state):
        """
        Prepare the faked partition, on top of the CPC created by
        setup_method().
        """
        self.partition_name = FAKED_PARTITION_1_NAME
        if initial_state in ('stopped', 'active'):
            # Create the partition (it is in stopped state by default)
            self.faked_partition = self.faked_cpc.partitions.add(
                FAKED_PARTITION_1)
            partitions = self.cpc.partitions.list()
            assert len(partitions) == 1
            self.partition = partitions[0]
            if initial_state == 'active':
                self.partition.start()
        else:
            self.faked_partition = None
            self.partition = None

    def setup_hba(self):
        """
        Prepare the faked HBA, on top of the faked partition created by
        setup_partition().
        """
        self.hba_name = FAKED_HBA_1_NAME
        if self.partition:
            # Create the HBA
            self.faked_hba = self.faked_partition.hbas.add(FAKED_HBA_1)
            hbas = self.partition.hbas.list()
            assert len(hbas) == 1
            self.hba = hbas[0]
        else:
            self.faked_hba = None
            self.hba = None

    def setup_nic(self):
        """
        Prepare the faked NIC, on top of the faked partition created by
        setup_partition().
        """
        self.nic_name = FAKED_NIC_1_NAME
        if self.partition:
            # Create the NIC
            self.faked_nic = self.faked_partition.nics.add(FAKED_NIC_1)
            nics = self.partition.nics.list()
            assert len(nics) == 1
            self.nic = nics[0]
        else:
            self.faked_nic = None
            self.nic = None

    @pytest.mark.parametrize(
        "check_mode", [False, True])
    @pytest.mark.parametrize(
        "initial_state", ['absent', 'stopped', 'active'])
    @pytest.mark.parametrize(
        "desired_state", ['absent', 'stopped', 'active'])
    @pytest.mark.parametrize(
        "properties, props_changed", [

            # special cases:
            (None, False),
            ({}, False),

            # allowed update-only properties:

            # TODO: Add a test for boot_network_nic_name (requires NIC):
            # ({'boot_network_nic_name': 'fake-nic-name'}, True),

            # TODO: Add a test for boot_storage_hba_name (requires HBA):
            # ({'boot_storage_hba_name': 'fake-hba-name'}, True),

            ({'acceptable_status': ['active', 'stopped', 'degraded']}, True),
            ({'processor_management_enabled': True}, True),
            ({'ifl_absolute_processor_capping': True}, True),
            ({'ifl_absolute_processor_capping_value': 0.9}, True),
            ({'ifl_processing_weight_capped': True}, True),
            ({'minimum_ifl_processing_weight': 10}, True),
            ({'maximum_ifl_processing_weight': 200}, True),
            ({'initial_ifl_processing_weight': 50}, True),
            ({'cp_absolute_processor_capping': True}, True),
            ({'cp_absolute_processor_capping_value': 0.9}, True),
            ({'cp_processing_weight_capped': True}, True),
            ({'minimum_cp_processing_weight': 10}, True),
            ({'maximum_cp_processing_weight': 200}, True),
            ({'initial_cp_processing_weight': 50}, True),
            ({'boot_logical_unit_number': '0123'}, True),
            ({'boot_world_wide_port_name': '0123456789abcdef'}, True),
            ({'boot_os_specific_parameters': 'fake'}, True),
            ({'boot_iso_ins_file': 'fake'}, True),
            # TODO: Add tests for SSC properties:
            # ({'ssc_boot_selection': 'fake'}, True),

            # allowed create+update properties:
            ({'description': 'fake'}, True),
            ({'short_name': 'fake'}, True),
            ({'partition_id': '7F'}, True),
            ({'autogenerate_partition_id': False}, True),
            ({'ifl_processors': 1}, False),
            ({'ifl_processors': 2}, True),
            ({'cp_processors': 0}, False),
            ({'cp_processors': 10}, True),
            ({'processor_mode': 'dedicated'}, True),
            ({'initial_memory': 2048}, True),
            ({'maximum_memory': 4096}, True),
            ({'reserve_resources': True}, True),
            ({'boot_device': 'ftp'}, True),
            ({'boot_timeout': 120}, True),
            ({'boot_ftp_host': 'fake'}, True),
            ({'boot_ftp_username': 'fake'}, True),
            ({'boot_ftp_password': 'fake'}, True),
            ({'boot_ftp_insfile': 'fake'}, True),
            ({'boot_removable_media': 'fake'}, True),
            ({'boot_removable_media_type': 'fake'}, True),
            ({'boot_configuration_selector': 'fake'}, True),
            ({'boot_record_lba': 12}, True),

            ({'access_global_performance_data': True}, True),
            ({'permit_cross_partition_commands': True}, True),
            ({'access_basic_counter_set': True}, True),
            ({'access_problem_state_counter_set': True}, True),
            ({'access_crypto_activity_counter_set': True}, True),
            ({'access_extended_counter_set': True}, True),
            ({'access_coprocessor_group_set': True}, True),
            ({'access_basic_sampling': True}, True),
            ({'access_diagnostic_sampling': True}, True),
            ({'permit_des_key_import_functions': False}, True),
            ({'permit_aes_key_import_functions': False}, True),
            # TODO: Add tests for SSC properties:
            # ({'ssc_host_name': 'fake'}, True),
            # ({'ssc_ipv4_gateway': 'fake'}, True),
            # ({'ssc_dns_servers': 'fake'}, True),
            # ({'ssc_master_userid': 'fake'}, True),
            # ({'ssc_master_pw': 'fake'}, True),
        ])
    @mock.patch("ansible.modules.zhmc.zhmc_partition.AnsibleModule",
                autospec=True)
    def test_success(
            self, ansible_mod_cls, properties, props_changed, desired_state,
            initial_state, check_mode):
        """
        Tests for successful operations on partition, dependent on
        parametrization.
        """

        # Prepare the initial partition before the test is run
        self.setup_partition(initial_state)

        # Set some expectations for this test from its parametrization
        exp_status = (PARTITION_STATUS_FROM_STATE[initial_state] if check_mode
                      else PARTITION_STATUS_FROM_STATE[desired_state])
        exp_part_exists = (initial_state != 'absent' if check_mode
                           else desired_state != 'absent')
        exp_part_returned = (desired_state != 'absent' and exp_part_exists)
        exp_changed = (initial_state != desired_state or
                       props_changed and desired_state != 'absent')

        # Prepare module input parameters
        params = {
            'hmc_host': 'fake-host',
            'hmc_auth': dict(userid='fake-userid',
                             password='fake-password'),
            'cpc_name': self.cpc.name,
            'name': self.partition_name,
            'state': desired_state,
            'properties': properties,
            'faked_session': self.session,
        }

        # Prepare mocks for AnsibleModule object
        mod_obj = mock_ansible_module(ansible_mod_cls, params, check_mode)

        # Exercise the code to be tested
        with pytest.raises(SystemExit) as exc_info:
            zhmc_partition.main()
        exit_code = exc_info.value.args[0]

        # Assert module exit code
        assert exit_code == 0, \
            "Module unexpectedly failed with this message:\n{}". \
            format(get_failure_msg(mod_obj))

        # Assert module output
        changed, part_props = get_module_output(mod_obj)
        assert changed == exp_changed
        if exp_part_returned:
            assert part_props != {}
            if not check_mode:
                assert part_props['status'] == exp_status
                assert part_props['name'] == params['name']
                if properties:
                    for prop_name in properties:
                        hmc_prop_name = prop_name.replace('_', '-')
                        assert part_props[hmc_prop_name] == \
                            properties[prop_name], \
                            "Property: {}".format(prop_name)
        else:
            assert part_props == {}

        # Assert the partition resource
        if not check_mode:
            parts = self.cpc.partitions.list()
            if exp_part_exists:
                assert len(parts) == 1
                part = parts[0]
                part.pull_full_properties()
                assert part.properties['status'] == exp_status
                assert part.properties['name'] == params['name']
                if properties:
                    for prop_name in properties:
                        hmc_prop_name = prop_name.replace('_', '-')
                        assert part.properties[hmc_prop_name] == \
                            properties[prop_name], \
                            "Property: {}".format(prop_name)
            else:
                assert len(parts) == 0

    @pytest.mark.parametrize(
        "check_mode", [False])
    @pytest.mark.parametrize(
        "initial_state", ['absent', 'stopped', 'active'])
    @pytest.mark.parametrize(
        "desired_state", ['stopped', 'active'])
    @pytest.mark.parametrize(
        "properties, test_when_created, test_when_modified", [
            # invalid properties (according to data model):
            ({None: 1}, True, True),
            ({'': 1}, True, True),
            ({'boo_invalid_prop': 1}, True, True),
            # valid properties specified with hyphens instead of underscores:
            ({'ifl-processors': 4}, True, True),
            # properties provided as module input parameter:
            ({'name': 'new-name'}, True, True),
            # create-only properties (tested only when modified):
            ({'type': 'ssc'}, False, True),
            # properties handled via their artificial properties:
            ({'boot_network_device': '/api/faked-nic-uri'}, True, True),
            ({'boot_storage_device': '/api/faked-hba-uri'}, True, True),
            # update-only properties (tested only when created):
            ({'boot_network_nic_name': 'faked-nic-name'}, True, False),
            ({'boot_storage_hba_name': 'faked-hba-name'}, True, False),
            # read-only properties:
            ({'object_uri': '/api/fake-partition-uri'}, True, True),
            ({'object_id': 'fake-oid'}, True, True),
            ({'parent': 'fake-parent'}, True, True),
            ({'class': 'fake-partition'}, True, True),
            ({'status': 'new-status'}, True, True),
            ({'has_unacceptable_status': False}, True, True),
            ({'is_locked': False}, True, True),
            ({'os_name': 'MyLinux'}, True, True),
            ({'os_type': 'Linux'}, True, True),
            ({'os_version': '3.10'}, True, True),
            ({'degraded_adapters': ''}, True, True),
            ({'current_ifl_processing_weight': 50}, True, True),
            ({'current_cp_processing_weight': 50}, True, True),
            ({'reserved_memory': 1024}, True, True),
            ({'auto_start': True}, True, True),
            ({'boot_iso_image_name': 'fake-iso-image-name'}, True, True),
            ({'threads_per_processor': 2}, True, True),
            ({'virtual_function_uris': ['/api/fake-vf-uri']}, True, True),
            ({'nic_uris': ['/api/fake-nic-uri']}, True, True),
            ({'hba_uris': ['/api/fake-hba-uri']}, True, True),
            ({'crypto_configuration': 'fake-config'}, True, True),
        ])
    @mock.patch("ansible.modules.zhmc.zhmc_partition.AnsibleModule",
                autospec=True)
    def test_error_properties(
            self, ansible_mod_cls, properties, test_when_created,
            test_when_modified, desired_state, initial_state, check_mode):
        """
        Test a property in the 'properties' module input parameter that is
        valid according to the data model, but not allowed for some reason.

        The invalidity is detected by the Ansible module, causing a module
        failure to be indicated with a "ParameterError" failure message.
        """

        # Skip tests for properties that are not to be tested when the
        # partition is being created or is being modified.
        is_created = (initial_state in ('absent',) and
                      desired_state in ('stopped', 'active'))
        if is_created and not test_when_created:
            return
        is_modified = (initial_state in ('stopped', 'active') and
                       desired_state in ('stopped', 'active'))
        if is_modified and not test_when_modified:
            return

        # Prepare the initial partition before the test is run
        self.setup_partition(initial_state)

        # Prepare module input parameters
        params = {
            'hmc_host': 'fake-host',
            'hmc_auth': dict(userid='fake-userid',
                             password='fake-password'),
            'cpc_name': self.cpc.name,
            'name': self.partition_name,
            'state': desired_state,
            'properties': properties,
            'faked_session': self.session,
        }

        # Prepare mocks for AnsibleModule object
        mod_obj = mock_ansible_module(ansible_mod_cls, params, check_mode)

        # Exercise the code to be tested
        with pytest.raises(SystemExit) as exc_info:
            zhmc_partition.main()
        exit_code = exc_info.value.args[0]

        # Assert module exit code
        assert exit_code == 1, \
            "Module unexpectedly succeeded with this output:\n" \
            "changed: {!r}, partition: {!r}". \
            format(*get_module_output(mod_obj))

        # Assert the failure message
        msg = get_failure_msg(mod_obj)
        assert msg.startswith("ParameterError:")

    @pytest.mark.parametrize(
        "check_mode", [False, True])
    @pytest.mark.parametrize(
        "initial_state", ['stopped', 'active'])
    @pytest.mark.parametrize(
        "desired_state", ['stopped', 'active'])
    @mock.patch("ansible.modules.zhmc.zhmc_partition.AnsibleModule",
                autospec=True)
    def test_boot_storage_success(
            self, ansible_mod_cls, desired_state, initial_state, check_mode):
        """
        Tests for successful configuration of boot from storage.
        """

        # Prepare the initial partition and HBA before the test is run
        self.setup_partition(initial_state)
        assert self.partition
        self.setup_hba()

        # Set some expectations for this test from its parametrization
        exp_status = (PARTITION_STATUS_FROM_STATE[initial_state] if check_mode
                      else PARTITION_STATUS_FROM_STATE[desired_state])

        properties = {
            'boot_device': 'storage-adapter',
            'boot_storage_hba_name': self.hba_name,  # artif. prop.
            'boot_logical_unit_number': '0002',
            'boot_world_wide_port_name': '1023456789abcdef',
        }

        exp_properties = {
            'boot_device': 'storage-adapter',
            'boot_storage_device': self.hba.uri,  # real prop for artif. prop.
            'boot_logical_unit_number': '0002',
            'boot_world_wide_port_name': '1023456789abcdef',
        }

        # Prepare module input parameters
        params = {
            'hmc_host': 'fake-host',
            'hmc_auth': dict(userid='fake-userid',
                             password='fake-password'),
            'cpc_name': self.cpc.name,
            'name': self.partition_name,
            'state': desired_state,
            'properties': properties,
            'faked_session': self.session,
        }

        # Prepare mocks for AnsibleModule object
        mod_obj = mock_ansible_module(ansible_mod_cls, params, check_mode)

        # Exercise the code to be tested
        with pytest.raises(SystemExit) as exc_info:
            zhmc_partition.main()
        exit_code = exc_info.value.args[0]

        # Assert module exit code
        assert exit_code == 0, \
            "Module unexpectedly failed with this message:\n{}". \
            format(get_failure_msg(mod_obj))

        # Assert module output
        changed, part_props = get_module_output(mod_obj)
        assert changed
        assert part_props != {}
        if not check_mode:
            assert part_props['status'] == exp_status
            assert part_props['name'] == params['name']
            for prop_name in exp_properties:
                hmc_prop_name = prop_name.replace('_', '-')
                assert part_props[hmc_prop_name] == \
                    exp_properties[prop_name], \
                    "Property: {}".format(prop_name)

        # Assert the partition resource
        if not check_mode:
            parts = self.cpc.partitions.list()
            assert len(parts) == 1
            part = parts[0]
            part.pull_full_properties()
            assert part.properties['status'] == exp_status
            assert part.properties['name'] == params['name']
            for prop_name in exp_properties:
                hmc_prop_name = prop_name.replace('_', '-')
                assert part.properties[hmc_prop_name] == \
                    exp_properties[prop_name], \
                    "Property: {}".format(prop_name)

    @pytest.mark.parametrize(
        "check_mode", [False, True])
    @pytest.mark.parametrize(
        "initial_state", ['stopped', 'active'])
    @pytest.mark.parametrize(
        "desired_state", ['stopped', 'active'])
    @mock.patch("ansible.modules.zhmc.zhmc_partition.AnsibleModule",
                autospec=True)
    def test_boot_storage_error_hba_not_found(
            self, ansible_mod_cls, desired_state, initial_state, check_mode):
        """
        Tests for successful configuration of boot from storage.
        """

        # Prepare the initial partition and HBA before the test is run
        self.setup_partition(initial_state)
        assert self.partition
        self.setup_hba()

        properties = {
            'boot_device': 'storage-adapter',
            'boot_storage_hba_name': 'invalid-hba-name',  # artif. prop.
            'boot_logical_unit_number': '0002',
            'boot_world_wide_port_name': '1023456789abcdef',
        }

        # Prepare module input parameters
        params = {
            'hmc_host': 'fake-host',
            'hmc_auth': dict(userid='fake-userid',
                             password='fake-password'),
            'cpc_name': self.cpc.name,
            'name': self.partition_name,
            'state': desired_state,
            'properties': properties,
            'faked_session': self.session,
        }

        # Prepare mocks for AnsibleModule object
        mod_obj = mock_ansible_module(ansible_mod_cls, params, check_mode)

        # Exercise the code to be tested
        with pytest.raises(SystemExit) as exc_info:
            zhmc_partition.main()
        exit_code = exc_info.value.args[0]

        # Assert module exit code
        assert exit_code == 1, \
            "Module unexpectedly succeeded with this output:\n" \
            "changed: {!r}, partition: {!r}". \
            format(*get_module_output(mod_obj))

        # Assert the failure message
        msg = get_failure_msg(mod_obj)
        assert msg.startswith("ParameterError:")

    @pytest.mark.parametrize(
        "check_mode", [False, True])
    @pytest.mark.parametrize(
        "initial_state", ['stopped', 'active'])
    @pytest.mark.parametrize(
        "desired_state", ['stopped', 'active'])
    @mock.patch("ansible.modules.zhmc.zhmc_partition.AnsibleModule",
                autospec=True)
    def test_boot_network_success(
            self, ansible_mod_cls, desired_state, initial_state, check_mode):
        """
        Tests for successful configuration of boot from network.
        """

        # Prepare the initial partition and HBA before the test is run
        self.setup_partition(initial_state)
        assert self.partition
        self.setup_nic()

        # Set some expectations for this test from its parametrization
        exp_status = (PARTITION_STATUS_FROM_STATE[initial_state] if check_mode
                      else PARTITION_STATUS_FROM_STATE[desired_state])

        properties = {
            'boot_device': 'network-adapter',
            'boot_network_nic_name': self.nic_name,  # artif. prop.
        }

        exp_properties = {
            'boot_device': 'network-adapter',
            'boot_network_device': self.nic.uri,  # real prop for artif. prop.
        }

        # Prepare module input parameters
        params = {
            'hmc_host': 'fake-host',
            'hmc_auth': dict(userid='fake-userid',
                             password='fake-password'),
            'cpc_name': self.cpc.name,
            'name': self.partition_name,
            'state': desired_state,
            'properties': properties,
            'faked_session': self.session,
        }

        # Prepare mocks for AnsibleModule object
        mod_obj = mock_ansible_module(ansible_mod_cls, params, check_mode)

        # Exercise the code to be tested
        with pytest.raises(SystemExit) as exc_info:
            zhmc_partition.main()
        exit_code = exc_info.value.args[0]

        # Assert module exit code
        assert exit_code == 0, \
            "Module unexpectedly failed with this message:\n{}". \
            format(get_failure_msg(mod_obj))

        # Assert module output
        changed, part_props = get_module_output(mod_obj)
        assert changed
        assert part_props != {}
        if not check_mode:
            assert part_props['status'] == exp_status
            assert part_props['name'] == params['name']
            for prop_name in exp_properties:
                hmc_prop_name = prop_name.replace('_', '-')
                assert part_props[hmc_prop_name] == \
                    exp_properties[prop_name], \
                    "Property: {}".format(prop_name)

        # Assert the partition resource
        if not check_mode:
            parts = self.cpc.partitions.list()
            assert len(parts) == 1
            part = parts[0]
            part.pull_full_properties()
            assert part.properties['status'] == exp_status
            assert part.properties['name'] == params['name']
            for prop_name in exp_properties:
                hmc_prop_name = prop_name.replace('_', '-')
                assert part.properties[hmc_prop_name] == \
                    exp_properties[prop_name], \
                    "Property: {}".format(prop_name)

    @pytest.mark.parametrize(
        "check_mode", [False, True])
    @pytest.mark.parametrize(
        "initial_state", ['stopped', 'active'])
    @pytest.mark.parametrize(
        "desired_state", ['stopped', 'active'])
    @mock.patch("ansible.modules.zhmc.zhmc_partition.AnsibleModule",
                autospec=True)
    def test_boot_network_error_hba_not_found(
            self, ansible_mod_cls, desired_state, initial_state, check_mode):
        """
        Tests for successful configuration of boot from network.
        """

        # Prepare the initial partition and HBA before the test is run
        self.setup_partition(initial_state)
        assert self.partition
        self.setup_nic()

        properties = {
            'boot_device': 'network-adapter',
            'boot_network_nic_name': 'invalid-nic-name',  # artif. prop.
        }

        # Prepare module input parameters
        params = {
            'hmc_host': 'fake-host',
            'hmc_auth': dict(userid='fake-userid',
                             password='fake-password'),
            'cpc_name': self.cpc.name,
            'name': self.partition_name,
            'state': desired_state,
            'properties': properties,
            'faked_session': self.session,
        }

        # Prepare mocks for AnsibleModule object
        mod_obj = mock_ansible_module(ansible_mod_cls, params, check_mode)

        # Exercise the code to be tested
        with pytest.raises(SystemExit) as exc_info:
            zhmc_partition.main()
        exit_code = exc_info.value.args[0]

        # Assert module exit code
        assert exit_code == 1, \
            "Module unexpectedly succeeded with this output:\n" \
            "changed: {!r}, partition: {!r}". \
            format(*get_module_output(mod_obj))

        # Assert the failure message
        msg = get_failure_msg(mod_obj)
        assert msg.startswith("ParameterError:")