# fontgoggles
FontGoggles: Visual OTL Preview and QA

## Build instructions

- Make sure you have Python 3.7 installed, preferably from python.org, but homebrew may work, too. (3.8 may work, but I didn't check whether all our dependencies are available.)

- Clone this repository.

- `cd` into the repository folder.

- Setup a virtual environment:

	`$ python3.7 -m venv venv --prompt=fontgoggles`

- Activate the environment:

	`$ source venv/bin/activate`

- Update `pip`:

	`$ pip install --upgrade pip`

- Install dependencies:

	`$ pip install -r requirements.txt`

- Install dev dependencies:

	`$ pip install -r requirements-dev.txt`

- Install our lib:

	`$ pip install .`

- Or, if you prefer an editable install of our lib:

	```
	$ pip install -e .
	$ ./Turbo/build_lib.sh
	```

    (The latter step builds a required C library, that otherwise wouldn't get built in editable mode.)

- Run some tests:

	`$ pytest`

- Build the application:

	`$ python App/setup.py py2app`

You'll find the built application in `App/dist/`

Now you can drop some fonts onto the app, or a folder containing fonts.
