FreshPass v.0.1.0
=======================

_Change all your passwords with one click._

**Important:** This is alpha-quality software. It will not misuse your passwords or leak them to third parties over the internet.
It may, however, leave unencrypted passwords on your local hard drive; lose new passwords after updating them;
or otherwise misbehave in frustrating ways. Please use at your own risk.

## Compatibility:

Operating Systems:

* Mac OS X (tested back to 10.6)
* Windows/Linux/etc. (untested, but Python source should be OS-independent)

Password Managers:

* 1Password 4
* 1Password 3 (but OS X Mavericks users will need to [change their Ruby path](https://discussions.agilebits.com/discussion/16149/1password-failed-to-run-import-script))

Accounts:

* Adobe
* Amazon
* Bank of America
* eBay
* Facebook
* Google
* LinkedIn
* Reddit
* Skype
* Twitter
* Yahoo
* Zillow

## Installation

### Mac

[Download Mac App](https://www.dropbox.com/s/ivcgrr3833ptvkz/FreshPass.app.zip)

### From Source (any OS)

1. Check out this repository.
2. [Download the PhantomJS binary](http://phantomjs.org/download.html) and place it in the contrib/ folder.
3. Install libyaml (optional):
    1. Mac: `brew install libyaml`
4. `pip install requirements.txt`
5. [Install the wxPython binary](http://www.wxpython.org/download.php)
6. `python source/main.py`

