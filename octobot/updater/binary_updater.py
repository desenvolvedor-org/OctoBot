#  Drakkar-Software OctoBot
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.
import json
import os
import enum

import aiofiles
import aiohttp

import octobot.constants as constants
import octobot.commands as commands
import octobot.updater.updater as updater_class
import octobot_commons.os_util as os_util
import octobot_commons.constants as commons_constants
import octobot_commons.aiohttp_util as aiohttp_util
import octobot_commons.enums as commons_enums


class DeliveryPlatformsName(enum.Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MAC = "osx"


class DeliveryPlatformsExtension(enum.Enum):
    WINDOWS = ".exe"
    LINUX = ""
    MAC = ""


class DeliveryArchitectureName(enum.Enum):
    X64_X86 = "x64"
    ARM_X64 = "arm_x64"


class BinaryUpdater(updater_class.Updater):
    BINARY_DELIVERY_SEPARATOR = "_"
    OLD_BINARY_SUFFIX = ".bak"
    NEW_BINARY_SUFFIX = ".new"

    async def get_latest_version(self):
        return self._parse_latest_version(await self._get_latest_release_data())

    async def update_impl(self):
        # self.aiohttp_session = aiohttp.ClientSession()
        new_binary_file = await self._download_binary()
        if new_binary_file is not None:
            self._move_binaries(commands.get_bot_file(), new_binary_file)

    def _get_latest_release_url(self):
        return f"{commons_constants.GITHUB_API_CONTENT_URL}/repos/" \
               f"{commons_constants.GITHUB_ORGANISATION}/" \
               f"{constants.OCTOBOT_BINARY_PROJECT_NAME}/releases/latest"

    async def _get_latest_release_data(self):
        try:
            async with aiohttp.ClientSession().get(self._get_latest_release_url()) as resp:
                text = await resp.text()
                if resp.status == 200:
                    return json.loads(text)
            return None
        except Exception as e:
            self.logger.debug(f"Error when fetching latest binary data : {e}")

    def _parse_latest_version(self, latest_release_data):
        try:
            return latest_release_data["tag_name"]
        except KeyError as e:
            self.logger.debug(f"Error when parsing latest binary version : {e}")
        return None

    async def _get_asset_from_release_data(self):
        latest_release_data = await self._get_latest_release_data()
        release_asset_name = self._create_release_asset_name(os_util.get_os())
        return release_asset_name, self._get_asset_from_name(latest_release_data, release_asset_name)

    def _get_asset_from_name(self, release_data, expected_asset_name):
        try:
            for asset in release_data["assets"]:
                asset_name, _ = os.path.splitext(asset["name"])
                if expected_asset_name == asset_name:
                    return asset
        except KeyError as e:
            self.logger.debug(f"Error when searching for {expected_asset_name} in latest release data : {e}")
        return None

    def _create_release_asset_name(self, platform):
        if platform is commons_enums.PlatformsName.WINDOWS:
            if os_util.is_machine_64bit():
                return f"{constants.PROJECT_NAME}{self.BINARY_DELIVERY_SEPARATOR}" \
                       f"{DeliveryPlatformsName.WINDOWS.value}{self.BINARY_DELIVERY_SEPARATOR}" \
                       f"{DeliveryArchitectureName.X64_X86.value}{DeliveryPlatformsExtension.WINDOWS.value}"
        elif platform is commons_enums.PlatformsName.MAC:
            if os_util.is_machine_64bit():
                if os_util.is_machine_64bit():
                    return f"{constants.PROJECT_NAME}{self.BINARY_DELIVERY_SEPARATOR}" \
                           f"{DeliveryPlatformsName.MAC.value}{self.BINARY_DELIVERY_SEPARATOR}" \
                           f"{DeliveryArchitectureName.X64_X86.value}{DeliveryPlatformsExtension.MAC.value}"
        elif platform is commons_enums.PlatformsName.LINUX:
            if os_util.is_machine_64bit():
                return f"{constants.PROJECT_NAME}{self.BINARY_DELIVERY_SEPARATOR}" \
                       f"{DeliveryPlatformsName.LINUX.value}{self.BINARY_DELIVERY_SEPARATOR}" \
                       f"{DeliveryArchitectureName.X64_X86.value}{DeliveryPlatformsExtension.LINUX.value}"
            elif os_util.is_arm_machine():
                return f"{constants.PROJECT_NAME}{self.BINARY_DELIVERY_SEPARATOR}" \
                       f"{DeliveryPlatformsName.LINUX.value}{self.BINARY_DELIVERY_SEPARATOR}" \
                       f"{DeliveryArchitectureName.ARM_X64.value}{DeliveryPlatformsExtension.LINUX.value}"
        return None

    async def _download_binary(self):
        release_asset_name, matching_asset_binary = await self._get_asset_from_release_data()
        new_binary_file = f"{release_asset_name}{self.NEW_BINARY_SUFFIX}"
        if matching_asset_binary is None:
            self.logger.error(f"Error when downloading latest version binary : Release not found on server")
            return None
        async with aiofiles.open(new_binary_file, 'wb+') as downloaded_file:
            await aiohttp_util.download_stream_file(output_file=downloaded_file,
                                                    file_url=matching_asset_binary["browser_download_url"],
                                                    aiohttp_session=aiohttp.ClientSession(),
                                                    is_aiofiles_output_file=True)
        return new_binary_file

    def _move_binaries(self, current_binary_file, new_binary_file):
        os.rename(current_binary_file, f"{current_binary_file}{self.OLD_BINARY_SUFFIX}")
        os.rename(new_binary_file, current_binary_file)