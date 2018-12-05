# Road map for Withings Open Humans data integration

- [ ] Fetch intraday data from Withings
- [ ] Data visualisation
- [ ] Allow user to specify which data they want to get
- [ ] Improve test coverage

## Done 🎉

- [x] Use OHAPI for s3 file storage
- [x] oauth1 workflow with Nokia API
- [x] get Nokia access tokens
- [x] get data from Nokia
- [x] upload data to Open Humans
- [x] deploy to Heroku/dokku
- [x] fix Celery issues
- [x] docs: readme, setup doc, contribution guidelines, code of conduct
- [x] tidy up code
- [x] Testing and automated tracking
  - [x] Sentry automated error tracking
  - [x] Travis continuous integration
  - [x] Hound linter
- [x] Rate limiting
  - [x] Try https://github.com/tomasbasham/ratelimit
  - [x] Look into requests-respectful
  - [x] Think about how to deal with intraday data limits
- [x] Get existing Withings members' tokens and get their data
