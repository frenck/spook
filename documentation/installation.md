---
subject: Getting started
title: Installing Spook in Home Assistant
subtitle: Don't worry, we'll go through it step-by-step.
short_title: Installing
thumbnail: images/social.png
description: Installing the most scary and powerful toolbox for Home Assistant isn't that hard. This step-by-step installation guide will help you through it.
numbering:
  heading_2: true
date: 2023-08-09T21:29:00+02:00
---

Time to get Spook 👻 settled and installed in your Home Assistant instance.

Getting Spook up and running should not be too hard when you follow this guide. If you run into issues during the installation, please check the[support](support) page on where to go for help.

## Requirements

Spook needs a few things to work properly, so let's go over them first.

1. Read, understand, and accept [the license](license) of Spook.
2. A working {term}`Home Assistant` instance running version **2023.7.0 or newer.**

   :::{note}
   The minimal required version of Home Assistant will change over time. This is not something to worry about. It is only important that you run at least the minimal required version of Home Assistant on the first installation of Spook.
   :::

3. You have the {term}`Home Assistant Community Store (HACS) <HACS>` installed.

   :::{hint} I don't have HACS installed. How do I do that? 👈
   :class: dropdown

   Installing HACS is easy, just follow the [official installation guide](https://hacs.xyz/docs/installation/manual).

   Or, if you are feeling lucky, run this script in an Home Assistant terminal to install HACS:

   ```shell
   wget -O - https://get.hacs.xyz | bash -
   ```

   :::

If you have met these requirements, you are ready to install Spook. 🎉

## Installation

Time to download and install Spook 👻 onto your Home Assistant instance.

:::{note}
HACS can be configured to run in two different modes: **standard** and **experimental**. Spook is available in both modes, but the installation process is differs slightly.
If you are using the **experimental** mode, be sure to select the **HACS with experimental mode enabled** tab below.
:::

:::{tip}
You can use select the {term}`My Home Assistant` button below, which will navigate you to Spook in HACS directly on your Home Assistant instance.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=frenck&repository=spook&category=integration)

You can directly go to step 6 if you use the button above (step 4 in case of using HACS experimental mode).
:::

::::{tab-set}

:::{tab-item} Standard HACS
:sync: standard

1. From the Home Assistant sidebar, select **HACS**. This will open the Home Assistant Community Store dashboard.
2. Select **Integrations**.

   ```{figure} images/installation/hacs_integrations.png
   :name: Open HACS and go to integrations
   :alt: Screenshot showing the HACS dashboard.
   :align: center

   Spook is an integration, so we need to go to the integrations page in HACS.
   ```

3. Select the **Explore & download repositories** button in the bottom right corner.
4. Select the search bar in the dialog shown and search for `Spook`.
5. Spook should now appear in the search results. Select it.

   ```{figure} images/installation/hacs_find_spook.png
   :name: Find and install Spook in HACS
   :alt: Screenshot showing the HACS dashboard searching for Spook.
   :align: center

   Finding Spook in the Home Assistant Community Store.
   ```

6. On the Spook page in HACS, select the **Download** button in the bottom right corner.

   ```{figure} images/installation/hacs_download_fab.png
   :name: Select the Download button on the Spook page in HACS
   :alt: Screenshot showing the Spook page in the HACS store.
   :align: center

   Select the big download button in the bottom right.
   ```

7. In the download dialog shown, select **Download** to download the Spook integration to your Home Assistant instance.

   ```{figure} images/installation/hacs_download.png
   :name: Download Spook in HACS
   :alt: Screenshot showing the download dialog in HACS.
   :align: center

   Download Spook in HACS.
   ```

8. After the download process has been completed, you need to restart Home Assistant in order for Home Assistant to see the new Spook integration.

   1. Select **Settings** from the sidebar, and then select **System**.
   2. Select the power button in the top right corner.
   3. Select **Restart Home Assistant** in the dialog that appears.

   ```{figure} images/installation/restart_home_assistant.png
   :name: Restart Home Assistant
   :alt: Screenshot showing the Home Assistant restart dialog.
   :align: center

   Restart Home Assistant.
   ```

:::

:::{tab-item} HACS with experimental mode enabled
:sync: experimental

1. From the Home Assistant sidebar, select **HACS**. This will open the Home Assistant Community Store dashboard.
2. Select the search bar at the top of the dashboard and search for `Spook`.
3. Spook should now appear in the search results. Select it.

   ```{figure} images/installation/hacs_experimental_find_spook.png
   :name: Find and install Spook in HACS
   :alt: Screenshot showing the HACS dashboard searching for Spook.
   :align: center

   Finding Spook in the Home Assistant Community Store.
   ```

4. On the Spook page in HACS, select the **Download** button in the bottom right corner.

   ```{figure} images/installation/hacs_experimental_download_fab.png
   :name: Select the Download button on the Spook page in HACS
   :alt: Screenshot showing the Spook page in the HACS store.
   :align: center

   Select the big download button in the bottom right.
   ```

5. In the download dialog shown, select **Download** to download the Spook integration to your Home Assistant instance.

   ```{figure} images/installation/hacs_experimental_download.png
   :name: Download Spook in HACS
   :alt: Screenshot showing the download dialog in HACS.
   :align: center

   Download Spook in HACS.
   ```

6. After the download process has been completed, you need to restart Home Assistant in order for Home Assistant to see the new Spook integration.

   1. Select **Settings** from the sidebar, and then select **System**.
   2. Select the power button in the top right corner.
   3. Select **Restart Home Assistant** in the dialog that appears.

   ```{figure} images/installation/experimental_restart_home_assistant.png
   :name: Restart Home Assistant
   :alt: Screenshot showing the Home Assistant restart dialog.
   :align: center

   Restart Home Assistant.
   ```

:::

::::

After Home Assistant has restarted, you are ready to activate the Spook integration.

## Activating the Spook integration

Now that Spook is installed, it is time to set up the integration in Home Assistant. This works exactly the as setting up any other integration in Home Assistant.

:::{tip}
You can use select the {term}`My Home Assistant` button below, which will take you directly take you to set up Spook on your Home Assistant instance.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=spook)

You can skip steps 1, 2, 3, and 4 if you use the button above.
:::

1. From the Home Assistant sidebar, select **Settings** and next select **Devices & Services**.
2. On the Devices & Services page, select the **+ Add integration** button in the bottom right corner.

   ```{figure} images/installation/add_integration.png
   :name: Add an integration to Home Assistant
   :alt: Screenshot showing the device & services page in Home Assistant.
   :align: center

   We are going to add a new integration to Home Assistant.
   ```

3. Select the search bar at the top of the dialog shown and search for `Spook`.
4. Spook should now appear in the search results. Select it.

   ```{figure} images/installation/find_spook.png
   :name: Find Spook in the integration search
   :alt: Screenshot showing showing the integration search dialog in Home Assistant.
   :align: center

   Finding the Spook integration to add to Home Assistant.
   ```

5. Confirm you have read, understood, and accepted [the license](license). Then select **Submit**.

   ```{figure} images/installation/accept_license.png
   :name: Accept the license
   :alt: Screenshot showing the Spook add integration dialog in Home Assistant.
   :align: center

   Only click submit if you have read, understood, and accepted the license of Spook.
   ```

6. It now takes a few seconds for the Spook integration to be set up, after which a success dialog will appear. Select **Finish** to close the dialog.

**🎉 You have successfully completed setting up Spook 👻 in Home Assistant. 🎉**
