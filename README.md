# Hired Labs, Inc. Main Website and Tools

This is the main website for Hired Labs, Inc. It serves as a platform for web applications and tools to help accomplish
our mission of ending veteran underemployment.

## Installation

### 1. Installation steps

### Linux/MacOS
#### 1.1. Clone the repository and move to working directory
```bash
git clone git@github.com:janton42/hl_main.git && cd hl_main
```

#### 1.2. Install dependencies and initialize virtual environment
```bash
pipenv install && pipenv shell
```

#### 1.3. Install MySQL

Refer to the MySql docs for details on installation and configuration. https://dev.mysql.com/doc/

#### 1.4. Create a database
```bash
mysql -u root -p
```

```sql
CREATE DATABASE HiredLabs;
quit;
```

Refer to this helpful MySql cheat sheet for more commands: https://devhints.io/mysql

#### 1.5. Create a .env file containing the environment variables below in the hl_main/ subdirectory

```bash
vi hl_main/.env
i # enter insert mode
DJANGO_SECRET_KEY=long-string-of-characters
DB_USER=username-you-created-in-MySql
DB_PASSWORD=password-you-created-in-MySql
q # quit insert mode
:wq # write and quit
```

#### 1.6. Run migrations
```bash
python3 manage.py migrate
```

#### 1.7. Load development seed data
```bash
python3 manage.py loaddata dev_data
```

#### 1.8. Run development server
```bash
python3 manage.py runserver
```

#### 1.9. Open localhost:8000 in your browser
##### Linux
```bash
 xdg-open http://127.0.0.1:8000/
```
##### MacOS
```bash
open http://127.0.0.1:8000/
```

#### Windows
Replace Windows with Linux, then follow the steps above.

## Usage
With the development server running, you'll be able to access the web apps by logging in with these credentials:

        username: admin
        password: admin

Your browser may warn you that this password is not secure. You can create another superuser with a more secure password,
if you wish. Simply run the command below and follow the prompts:

```bash
python3 manage.py createsuperuser 
```

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss the change. Please see
CODE_OF_CONDUCT.md for details on our code of conduct.

[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](code_of_conduct.md)
## License
[GPL-3.0 license](https://www.gnu.org/licenses/gpl-3.0.en.html)
