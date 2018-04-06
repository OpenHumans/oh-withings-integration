# Road map for Nokia Health to Open Humans data integration

## Short term: first release

- [ ] Testing and automated tracking
  - [x] Sentry automated error tracking
  - [x] Travis continuous integration
  - [ ] Hound linter
  - [ ] VCR http request testing
- [ ] Rate limiting
  - [ ] Try https://github.com/tomasbasham/ratelimit
  - [ ] Look into requests-respectful
  - [ ] Think about how to deal with intraday data limits
- [ ] Get existing Withings members' tokens and get their data

## Long term: v2

- [ ] Data visualisation
- [ ] Use OHAPI for s3 file storage
- [ ] Allow user to specify which data they want to get
- [ ] Improve test coverage

## Done 🎉

- [x] oauth1 workflow with Nokia API
- [x] get Nokia access tokens
- [x] get data from Nokia
- [x] upload data to Open Humans
- [x] deploy to Heroku/dokku
- [x] fix Celery issues
- [x] docs: readme, setup doc, contribution guidelines, code of conduct
- [x] tidy up code
