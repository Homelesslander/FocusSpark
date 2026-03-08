# MySQL Setup Guide for ADHD App

## Local Testing Setup (What to do now)

### Step 1: Download & Install MySQL
1. Go to https://dev.mysql.com/downloads/mysql/
2. Download "MySQL Community Server" for Windows (latest version)
3. Run the installer
4. When prompted, choose:
   - Setup Type: **Developer Default** (or Custom, just make sure MySQL Server 8.0 is selected)
   - Config Type: **Development Machine**
   - MySQL Port: **3306** (default)
   - Root password: **Set something you remember** (example: `admin123`)
   - MySQL Service Name: **MySQL80** (or whatever version)
   - Click Install, wait for it to complete

### Step 2: Create Database & User
1. Open **MySQL Command Line Client** (search for it in Windows Start menu)
2. When prompted, enter the root password you set above
3. Copy and paste these commands one at a time:

```sql
CREATE DATABASE adhd_app;
CREATE USER 'adhd_user'@'localhost' IDENTIFIED BY 'adhd_password_123';
GRANT ALL PRIVILEGES ON adhd_app.* TO 'adhd_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### Step 3: The credentials are already in the code!
The `db_config.py` file is already set with these values:
- **host**: localhost
- **user**: adhd_user
- **password**: adhd_password_123
- **database**: adhd_app

The app will now connect to your local MySQL database automatically!

### Step 4: Run Your App
```bash
python app.py
```

The app will automatically create all tables when it starts. Go to `http://localhost:5050` in your browser.

---

## Testing the App Locally
- Create accounts, add tasks, complete them - everything works the same
- Your data is now stored in MySQL instead of SQLite
- This is exactly what will happen on GoDaddy

---

## When You're Ready for GoDaddy

1. Purchase GoDaddy shared hosting with your domain
2. In GoDaddy control panel, create a MySQL database
3. GoDaddy will give you: **database name**, **username**, **password**, **host**
4. Update `db_config.py` with those values:
   ```python
   DB_CONFIG = {
       'host': 'mysql.YOURDOMAINNAME.com',  # GoDaddy will give you this
       'user': 'your_godaddy_user',
       'password': 'your_godaddy_password',
       'database': 'your_godaddy_database'
   }
   ```
5. Upload the entire folder to GoDaddy
6. It works - no code changes needed!

---

## Troubleshooting

**Error: "Access denied for user 'adhd_user'@'localhost'"**
- Make sure you ran the CREATE USER and GRANT commands above
- Check that the password is exactly `adhd_password_123`

**Error: "Can't connect to MySQL server"**
- Make sure MySQL Server is actually running
- Windows: Search "Services" → Find "MySQL80" → Make sure it says "Running"
- If not running, right-click it → Start

**Error: "Unknown database 'adhd_app'"**
- Make sure you ran the `CREATE DATABASE adhd_app;` command

---

## Quick Check: Is MySQL Working?

Open Command Prompt and run:
```bash
mysql -u adhd_user -p -h localhost
```

When prompted, enter password: `adhd_password_123`

If you see `mysql>` prompt, you're good! Type `EXIT;` to quit.
