---
subject: Getting started
title: Installing Spook in Home Assistant
subtitle: Don't worry, we'll go through it step-by-step.
short_title: Installing
thumbnail: images/social.png
description: Installing the most scary and powerful toolbox for Home Assistant isn't that hard. This step-by-step installation guide will help you through it.
numbering:
  heading_2: true
date: 2024-02-10T14:39:21+01:00
---

Time to get Spook 👻 settled and installed in your Home Assistant instance.

Getting Spook up and running should not be too hard when you follow this guide. If you run into issues during the installation, please check the [support](support) page on where to go for help.

## Requirements

Spook needs a few things to work properly, so let's go over them first.

1. Read, understand, and accept [the license](license) of Spook.
2. A working {term}`Home Assistant` instance running version **2025.2.0 or newer.**

   :::{note}
   The minimal required version of Home Assistant will change over time. This is not something to worry about. It is only important that you run at least the minimal required version of Home Assistant on the first installation of Spook.
   :::

3. You have the {term}`Home Assistant Community Store (HACS) <HACS>` installed.

   :::{hint} I don't have HACS installed. How do I do that? 👈
   :class: dropdown

   If you don't have HACS installed yet, please follow the [official installation guide](https://hacs.xyz/docs/installation/manual).
   :::

If you have met these requirements, you are ready to install Spook. 🎉

## Installation

Time to download and install Spook 👻 onto your Home Assistant instance.

1. From the Home Assistant sidebar, select **HACS**. This will open the Home Assistant Community Store dashboard.
2. Select the search bar at the top of the dashboard and search for `Spook`.
3. Spook should now appear in the search results. Select it.

   ```{figure} images/installation/hacs_experimental_find_spook.png
   :alt: Screenshot showing the HACS dashboard searching for Spook.
   :align: center
   ```

4. On the Spook page in HACS, select the **Download** button in the bottom right corner.

   ```{figure} images/installation/hacs_experimental_download_fab.png
   :alt: Screenshot showing the Spook page in the HACS store.
   :align: center
   ```

5. In the download dialog shown, select **Download** to download the Spook integration to your Home Assistant instance.

   ```{figure} images/installation/hacs_experimental_download.png
   :alt: Screenshot showing the download dialog in HACS.
   :align: center
   ```

6. After the download process has been completed, you need to restart Home Assistant in order for Home Assistant to see the new Spook integration.

   1. Select **Settings** from the sidebar, and then select **System**.
   2. In the top right corner select the power button
   3. Select **Restart Home Assistant** in the dialog that appears.

   ```{figure} images/installation/experimental_restart_home_assistant.png
   :alt: Screenshot showing the Home Assistant restart dialog.
   :align: center
   ```

After Home Assistant has restarted, you are ready to activate the Spook integration.

## Activating the Spook integration

Now that Spook is installed, it is time to set up the integration in Home Assistant. This works exactly the as setting up any other integration in Home Assistant.

1. From the Home Assistant sidebar, select **Settings** and next select **Devices & Services**.
2. On the Devices & Services page, in the bottom right corner, select the **+ Add integration** button.

   ```{figure} images/installation/add_integration.png
   :alt: Screenshot showing the device & services page in Home Assistant.
   :align: center
   ```

3. Select the search bar at the top of the dialog shown and search for `Spook`.
4. Spook should now appear in the search results. Select it.

   ```{figure} images/installation/find_spook.png
   :alt: Screenshot showing showing the integration search dialog in Home Assistant.
   :align: center
   ```

5. Confirm you have read, understood, and accepted [the license](license). Then select **Submit**.

   ```{figure} images/installation/accept_license.png
   :alt: Screenshot showing the Spook add integration dialog in Home Assistant.
   :align: center
   ```

6. It now takes a few seconds for the Spook integration to be set up, after which a success dialog will appear. Select **Finish** to close the dialog.

**🎉 You have successfully completed setting up Spook 👻 in Home Assistant. 🎉**
