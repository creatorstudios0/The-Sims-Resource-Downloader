# GitHub Upload Checklist

Use Git from the project root when possible so `.gitignore` keeps local runtime files out of the repository.

```sh
git init
git add .gitignore .github LICENSE NOTICE.md README.md requirements.txt setup.bat start.bat src
git commit -m "Prepare Infinity production build"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Do not upload these local runtime folders/files:

- `venv/`
- `Downloads/`
- `logs.log`
- `src/logs.log`
- `src/urls.txt`
- `src/session`
- `src/__pycache__/`

After creating the repository, check the Actions tab. The `Python Check` workflow should pass.
