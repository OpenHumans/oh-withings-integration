# Open Humans Withings data integration project

[![Build Status](https://travis-ci.org/OpenHumans/oh-nokiahealth-integration.svg?branch=master)](https://travis-ci.org/OpenHumans/oh-nokiahealth-integration)

*This is a Django/Celery application which takes the user through authorization steps with Open Humans and Withings (formerly Nokia Health) and and then adds raw data from their Withings account data into their Open Humans account.*

The app is live at: [https://withings.openhumans.org](https://withings.openhumans.org)

This repo is based on the Open Humans [data demo template project](https://github.com/OpenHumans/oh-data-demo-template). It uses the [Withings API](http://developer.withings.com/oauth2) to get personal body, sleep, and activity data.

If you would like to contribute to this project, please check out our [contribution guidelines](CONTRIBUTING.md) and the [roadmap](ROADMAP.md).
