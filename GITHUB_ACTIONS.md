# بناء Windows عبر GitHub Actions

الملف `.github/workflows/windows-build.yml` يعمل يدويًا فقط عبر `workflow_dispatch`، على `windows-latest` مع Python 3.12 x64. يشغّل `build_windows.py` الحالي: تثبيت الاعتماديات، الاختبارات، PyInstaller، التغليف والتحقق من ZIP. فشل أي مرحلة يوقف المهمة؛ لا تُرفع الحزمة إلا بعد النجاح. بعد موافقة المستخدم على نشر الكود في مستودع Public على حساب `abdulkader000`، أزيل شرط المستودع الخاص؛ يعمل الـworkflow مع المستودعات العامة والخاصة. مفاتيح API تبقى محلية ولا تُرفع في الحالتين.

اسم الـartifact هو `TextGenerator-Windows`، ويحتوي `TextGenerator_Windows.zip`. داخل ZIP توجد فقط هذه الملفات في الجذر، دون مجلد إضافي:

```text
TextGenerator.exe
.env
ANLEITUNG.txt
```

ملف `.env` داخل الحزمة يولّد من إعداد ثابت بمفتاح `YOUR_API_KEY_HERE` ونفس النموذج `gpt-4`. لا ينسخ البناء `.env` المحلي ولا `.env.example`. يُفحص عدد الملفات وأسماؤها وسلامة ZIP والإعداد الثابت وترويسة EXE قبل اعتبار البناء ناجحًا. لا توجد GitHub Secrets لمفتاح OpenAI ولا طلبات توليد حقيقية أثناء البناء.

## الحالة قبل الرفع

عند إعداد هذه الملفات، لم يكن المجلد مستودع Git ولم يوجد remote مرتبط، ولم يكن `gh` مثبتًا. لم ينفذ Codex إنشاء مستودع أو commit أو push أو تشغيل workflow. شُغلت الاختبارات التسعة محليًا على macOS بنجاح، وفُحص YAML وإعداد الـworkflow وقواعد الاستبعاد؛ لم يُجر بعد بناء Windows على GitHub.

في الفحص اللاحق أصبح `gh` مثبتًا بإصدار 2.102.0، لكنه لم يكن مسجل الدخول بعد. المجلد لا يزال غير مرتبط بمستودع.

## تسجيل الدخول بالحساب العادي دون إنشاء توكن يدوي

التوكن رمز تفويض لحساب GitHub، وليس مفتاح OpenAI. يمكن للمستخدم تسجيل الدخول بنفسه عبر المتصفح، ويُنشئ GitHub CLI التفويض تلقائيًا. Codex لا يتحكم بالمتصفح أو بواجهة تسجيل الدخول. نفّذ هذا الأمر محليًا:

```zsh
gh auth login --hostname github.com --git-protocol https --web --scopes workflow
```

انسخ الرمز القصير الذي يعرضه Terminal إلى صفحة GitHub التي تفتح، وسجل الدخول بحساب `abdulkader000` ثم وافق على تفويض GitHub CLI. بعدها:

```zsh
gh auth setup-git
gh auth status
```

`gh auth setup-git` يربط Git بالمصادقة الموجودة؛ لا يسجل الدخول بحد ذاته. لا ترسل أي رمز أو توكن في المحادثة.

## تثبيت CLI والمصادقة النصية محليًا

على هذا الجهاز الذي يستخدم macOS وzsh:

```zsh
brew install gh
gh auth status
```

إذا لم يكن GitHub مسجل الدخول، استخدم رمز GitHub محليًا عبر الإدخال المخفي، دون متصفح. هذا رمز GitHub وليس مفتاح OpenAI. للمصادقة بـPAT classic يلزم `repo` و`read:org` و`gist` بحسب توثيق CLI، مع `workflow` لرفع ملف الـworkflow. لا ترسل الرمز في المحادثة ولا تكتبه داخل ملفات المشروع أو الأوامر حرفيًا:

```zsh
read -rs 'pohlmann_github_token?GitHub token (local input): '
printf '%s' "$pohlmann_github_token" | gh auth login --hostname github.com --git-protocol https --with-token
unset pohlmann_github_token
gh auth setup-git
```

## أوامر الرفع التي ينفذها المستخدم

هذه الأوامر للمجلد الحالي غير المرتبط بمستودع، بعد تسجيل الدخول بحساب `abdulkader000`. إنشاء المستودع يستخدم `--public` بموافقة المستخدم، دون `--push`؛ الرفع منفصل وينفذه المستخدم. إذا كان الاسم مستخدمًا بالفعل، لا تتابع أوامر الرفع؛ حدد أولًا المستودع المقصود.

```zsh
(
set -e
cd /Users/abdulkaderalamin/Documents/Code/pohlmann-textgenerator
git init -b main
git add .github/workflows/windows-build.yml .gitignore .env.example \
  app.py app.spec text_engine.py site_data.json templates tests \
  requirements.txt build_windows.py BUILD_WINDOWS.bat ANLEITUNG.txt \
  README.md PRUEFBERICHT.md GITHUB_ACTIONS.md
git diff --cached --stat
git commit -m "Add manual Windows EXE build workflow"
gh repo create abdulkader000/pohlmann-textgenerator --public --source=. --remote=origin
gh repo view --json nameWithOwner,isPrivate
git push -u origin main
gh repo edit --default-branch main
)
```

إذا توقف commit لغياب هوية Git، اضبط الاسم والبريد الصحيحين محليًا بـ`git config user.name` و`git config user.email` ثم أعد commit. لا تتابع عند أي خطأ. لا ترفع `.env` أو أي مفتاح محلي، ولا تغيّر `.env.example` إلى مفتاح حقيقي.

ملف الـworkflow يجب أن يكون موجودًا في الفرع الافتراضي حتى يقبل GitHub `workflow_dispatch`. الـpush وحده لا يشغّل هذا الـworkflow.

## بعد تأكيد تنفيذ push

أخبر Codex بأنك نفذت push مع اسم المستودع `OWNER/REPO`. عندها يتحقق Codex باستخدام CLI من هوية المستودع ومن commit الذي سيتم بناؤه، ويشغّل الـworkflow، ثم يتابع نتيجة التشغيل المحدد وينزل الـartifact الخاص به. الأوامر الأساسية المستخدمة في تلك المرحلة هي:

```zsh
gh workflow run windows-build.yml --ref main
gh run list --workflow windows-build.yml --event workflow_dispatch --branch main --limit 5
gh run watch RUN_ID --exit-status
gh run download RUN_ID --name TextGenerator-Windows --dir release
.venv/bin/python -c 'from pathlib import Path; from build_windows import validate_archive; validate_archive(Path("release/TextGenerator_Windows.zip"))'
```

`RUN_ID` يستبدل برقم التشغيل الذي أُطلق بالفعل؛ لا تختَر artifact من تشغيل قديم. لا تنفذ هذه المرحلة الآن إذا كنت تريد أن يتولاها Codex بعد تأكيد الرفع. تنزيل artifact محدد عبر `gh` يفك الغلاف الذي أنشأته Action ويبقي ZIP الخاصة بالمستلمة. يقدّم Codex المسار المطلق للحزمة التي نُزلت وفُحصت بالفعل؛ المسار المتوقع هنا هو `/Users/abdulkaderalamin/Documents/Code/pohlmann-textgenerator/release/TextGenerator_Windows.zip`، وهي غير موجودة بعد في هذه المرحلة.

## حدود الاختبار

نجاح Actions يثبت نجاح الاختبارات والبناء والتغليف فقط. لا يثبت تشغيل واجهة EXE، ولا فتح المتصفح الحقيقي، ولا التشغيل دون نافذة Terminal. تبقى تجربة EXE على جهاز Windows مطلوبة، بما فيها مسار مع مسافات، Demo، كلا التنزيلين، الإنهاء وإعادة التشغيل. بعد تعبئة رصيد API وإضافة المفتاح محليًا بجوار EXE، يجب توليد مقالين حقيقيين وفحص 720–880 كلمة عند هدف 800، جميع الروابط، قابلية القراءة وتنوع الصياغة. تبقى التسليمات أولية حتى إجراء هذه الاختبارات.

## التوثيق الرسمي الذي تم التحقق منه

تم التحقق في 6 أكتوبر 2026 من أمثلة الاستخدام وملفات `action.yml` الرسمية:

- [actions/checkout v7](https://github.com/actions/checkout): `persist-credentials: false` وصلاحية `contents: read`.
- [actions/setup-python v7](https://github.com/actions/setup-python): `python-version` و`architecture`؛ استخدمنا 3.12 وx64.
- [actions/upload-artifact v7](https://github.com/actions/upload-artifact): `path` و`name` و`if-no-files-found: error` و`compression-level` و`retention-days`. ملف ZIP نفسه يرفع كملف واحد، دون رفع مجلد المشروع.
- [التشغيل اليدوي](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow): `workflow_dispatch` وشرط وجود الملف في الفرع الافتراضي.
- [إنشاء مستودع عبر gh](https://cli.github.com/manual/gh_repo_create)، [المصادقة النصية](https://cli.github.com/manual/gh_auth_login)، [تشغيل workflow](https://cli.github.com/manual/gh_workflow_run)، [متابعة التشغيل](https://cli.github.com/manual/gh_run_watch)، [تنزيل artifact](https://cli.github.com/manual/gh_run_download).
