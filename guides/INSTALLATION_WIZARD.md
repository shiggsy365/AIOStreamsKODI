# Installing AIOStreams for KODI

This guide covers the installation and initial setup of the AIOStreams plugin and skin for Kodi.

## Before You Start

To get the most out of AIOStreams, you will need several API keys and credentials. We recommended setting these up beforehand:

- **Trakt.tv**: For the AIOStreams plugin, it is highly recommended to have a **Trakt Client ID** and **Client Secret**.
  - Create a Trakt app here: [https://trakt.tv/oauth/applications/new](https://trakt.tv/oauth/applications/new)
- **YouTube API**: For the AIOStreams skin visuals (trailers, etc.), it is recommended to have a **YouTube API Key**, **Client ID**, and **Secret**.
  - Follow the instructions here: [YouTube Setup Guide](https://github.com/anxdpanic/plugin.video.youtube/issues/1095)
- **IMVDb** (Optional): If you wish to use the IMVDb features, obtain a key here: [https://imvdb.com/](https://imvdb.com/)

---

## Overview

**AIOStreams for KODI** is a comprehensive solution for managing and streaming your media library. It consists of:

1.  **The Plugin (`plugin.video.aiostreams`)**: The engine that communicates with your AIOStreams backend, handles searching, stream selection, and Trakt integration.
2.  **The Skin (`skin.AIODI`)**: A premium, custom-built interface designed specifically to showcase content from AIOStreams with rich metadata and dynamic widgets.

---

## Operational Options

You can choose how to run AIOStreams based on your preference:

- **Standalone Plugin**: Use the AIOStreams plugin with any standard Kodi skin. You will access content through the "Add-ons" menu.
- **TMDB Helper Integration**: Run AIOStreams within a skin that supports **TMDB Helper** using custom players. This allows you to use AIOStreams as a playback source for other library-focused skins.
- **Full Custom Built Skin (AIODI)**: The recommended experience. Running AIOStreams within the dedicated AIODI skin provides the most seamless integration, with heavy use of widgets and specialized layouts.

---

## Installation Steps

### 1. Add Repository Source
To receive automatic updates, add the official repository to your Kodi:

1.  Open Kodi and go to **Settings (Gear Icon) > File Manager**.
2.  Select **Add Source**.
3.  Enter the URL: `https://shiggsy365.github.io/AIOStreamsKODI/`
4.  Name the source `AIOStreams`.
5.  Go back to **Settings > Add-ons > Install from zip file**.
6.  Select `AIOStreams` and install the `repository.aiostreams.zip`.

### 2. Install Plugin and Skin
1.  Go to **Settings > Add-ons > Install from repository**.
2.  Select **AIOStreams Repository**.
3.  Go to **Program add-ons** and install **Onboarding Wizard**.

### 3. Running the Onboarding Wizard
The Onboarding Wizard, when run, will guide you through all of the setup steps for whichever experiance you decided on.
- Entering your AIOStreams Backend URL credentials.
- Authorizing your Trakt account.
- Initializing basic settings for playback quality and language.
- Downloading TMDBHelper Players
- Installing all plugins and skins
When running the wizard, the only on screen prompt you need to interact with is the Trakt Authorisation prompt. Ignore all other pop-ups
Once complete, restart Kodi, open the YouTube addon to sign in (if installed), customise your home screen widgets (left arrow from the settings icon) and restart kodi one last time

### 4. Customizing Your Home Screen
If you are using the AIODI skin, you can manage your home screen layout using the built-in **Widget Manager**:
- Access the Widget Manager via **Home Screen > Press left from settings icon > Widget Manager**.
- Arrange your Trakt lists, AIOStreams catalogs, and more to create a personalized dashboard.
