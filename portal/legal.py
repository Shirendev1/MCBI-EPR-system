"""Legal pages of the MCBI EPR portal: privacy policy, terms of use, legal notice.

The company details come from environment variables so that nothing personal
or company-specific is hard-coded in the public repository:

    LEGAL_COMPANY_ADDRESS   registered address of the company        (required)
    LEGAL_COMPANY_REG_NO    company registration number              (required)
    LEGAL_CONTACT_EMAIL     contact and privacy e-mail address       (required)
    LEGAL_HOSTING_REGION    where the server and database run,
                            for example "Frankfurt, Germany (EU)"    (required)
    LEGAL_COMPANY_NAME      legal name (has a default)
    LEGAL_REPRESENTATIVE    person who represents the company (has a default)
    LEGAL_REVIEWED          set to "true" after a lawyer has reviewed the texts

While a required value is missing, or LEGAL_REVIEWED is not "true", every
legal page shows a "draft" notice at the top. That keeps the pages honest
until they are complete.

When the texts change in a way users must accept again, change
LEGAL_VERSION. New organizations store the version they accepted.
"""

import html
import os

LEGAL_VERSION = "2026-10-29"

REQUIRED = ("LEGAL_COMPANY_ADDRESS", "LEGAL_COMPANY_REG_NO",
            "LEGAL_CONTACT_EMAIL", "LEGAL_HOSTING_REGION")

DEFAULTS = {
    "LEGAL_COMPANY_NAME": "Mongolia Circular Battery Initiative LLC "
                          "(«Монголын тойрог батарейн санаачилга» ХХК)",
    "LEGAL_REPRESENTATIVE": "Enkhtsetseg Shirendev (Ширэндэвийн Энхцэцэг), "
                            "Founder and CEO",
}

PAGES = ("privacy", "terms", "impressum")


def _value(name, lang):
    value = (os.getenv(name) or DEFAULTS.get(name) or "").strip()
    if value:
        return html.escape(value)
    missing = "[not yet provided]" if lang == "en" else "[одоогоор оруулаагүй]"
    return f'<span class="missing">{missing}</span>'


def is_complete():
    return all((os.getenv(n) or "").strip() for n in REQUIRED)


def is_final():
    return is_complete() and (os.getenv("LEGAL_REVIEWED") or "").lower() == "true"


def _fields(lang):
    return {
        "company": _value("LEGAL_COMPANY_NAME", lang),
        "address": _value("LEGAL_COMPANY_ADDRESS", lang),
        "reg_no": _value("LEGAL_COMPANY_REG_NO", lang),
        "rep": _value("LEGAL_REPRESENTATIVE", lang),
        "email": _value("LEGAL_CONTACT_EMAIL", lang),
        "region": _value("LEGAL_HOSTING_REGION", lang),
        "version": LEGAL_VERSION,
    }


# ----------------------------------------------------------------------
# TEXTS  (one HTML body per page and language; {placeholders} are filled
# from _fields). Keep the English and Mongolian versions in step.
# ----------------------------------------------------------------------

TEXTS = {
    "en": {
        "nav_privacy": "Privacy policy",
        "nav_terms": "Terms of use",
        "nav_impressum": "Legal notice",
        "nav_portal": "Back to the portal",
        "other_lang": "Монгол",
        "draft": "Draft. This page is still being completed and has not yet "
                 "been reviewed by a lawyer.",
        "updated": "Version {version}",

        "privacy_title": "Privacy policy",
        "privacy": """
<p>This policy explains what personal data the MCBI EPR pilot portal
(passport.mcbis.org) processes, why, and what rights you have. The portal is
a pilot: it is used for testing a battery registration and battery passport
system and does not collect payments.</p>

<h2>1. Who is responsible</h2>
<p>{company}<br>{address}<br>Registration number: {reg_no}<br>
E-mail: {email}</p>
<p>We have not appointed a data protection officer. Please send all privacy
questions to the e-mail address above.</p>

<h2>2. Two different roles</h2>
<ul>
<li><strong>Organization accounts.</strong> For the data needed to run your
organization's account, MCBI decides how the data is used and is the
<em>controller</em>.</li>
<li><strong>Battery records.</strong> Batteries are registered by
organizations. For those records MCBI processes data on behalf of the
registering organization and is its <em>processor</em>. Most battery data is
technical and is not personal data. Where a record contains personal data
(for example a contact address of a sole trader), the registering
organization is the controller and a data processing agreement applies.</li>
</ul>

<h2>3. What data we process</h2>
<table>
<tr><th>Data</th><th>Purpose</th><th>Legal basis (GDPR)</th></tr>
<tr><td>Organization name, e-mail address, organization type, country,
date of sign-up</td><td>Creating and running your account, approving
organizations, contacting you about the pilot</td><td>Art. 6(1)(b):
contract</td></tr>
<tr><td>Password</td><td>Signing in. We store only a one-way hash
(PBKDF2-SHA256), never the password itself.</td><td>Art. 6(1)(b):
contract</td></tr>
<tr><td>Date and version of the terms you accepted</td><td>Proving that the
terms and this policy were accepted</td><td>Art. 6(1)(c) and (f): legal
obligation, legitimate interest</td></tr>
<tr><td>Failed sign-in attempts (e-mail address and time)</td><td>Protecting
accounts against password guessing. Kept in working memory for at most
15 minutes and lost when the server restarts.</td><td>Art. 6(1)(f):
legitimate interest in security</td></tr>
<tr><td>Technical access data (IP address, time, requested page, browser
type) in the hosting provider's server logs</td><td>Operating the service,
finding faults, preventing abuse</td><td>Art. 6(1)(f): legitimate interest in
a secure and working service</td></tr>
<tr><td>Battery records and their history</td><td>Providing the battery
registration and passport service to the registering organization</td>
<td>On behalf of the registering organization (Art. 28)</td></tr>
</table>
<p>Visitors who only scan a QR code or look up a battery do not need an
account. They see only the public fields of a record.</p>

<h2>4. Cookies and tracking</h2>
<p>The portal does not use advertising, analytics or tracking cookies and does
not use external web fonts. It uses only the technical storage that the
application needs to work, such as keeping a page session open. The usage
statistics of the Gradio framework are switched off.</p>

<h2>5. Where the data is stored and who receives it</h2>
<p>The portal and its database are hosted by Render Services, Inc.,
525 Brannan St, San Francisco, CA 94131, USA, in the region
<strong>{region}</strong>. Render processes the data on our behalf under its
<a href="https://render.com/dpa">Data Processing Addendum</a>. Render is a
US company, so access from outside the EU cannot be ruled out. For such
transfers the addendum relies on the EU-U.S. Data Privacy Framework and, as a
fallback, on the EU Standard Contractual Clauses. Render's own subprocessors
are listed on its <a href="https://render.com/trust">trust page</a>.</p>
<p>The domain name system (DNS) of mcbis.org is managed by Hostinger. DNS only
directs browsers to the server; Hostinger does not receive the content of
the portal.</p>
<p>We do not sell personal data and do not pass it to anyone else, unless we
are legally required to.</p>

<h2>6. How long we keep data</h2>
<ul>
<li>Account data: as long as the account exists. After you ask us to close
the account, we delete it within 30 days, unless the law requires us to keep
it longer.</li>
<li>Failed sign-in attempts: at most 15 minutes.</li>
<li>Server logs: as long as the hosting provider keeps them under its
standard settings.</li>
<li>Battery records: as agreed with the registering organization. Under the
EU Battery Regulation (EU) 2023/1542, a battery passport must stay available
for the life of the battery, so passport data may need to be kept longer
than the account.</li>
</ul>

<h2>7. Your rights</h2>
<p>You have the right to access your data, to have it corrected or deleted,
to restrict its processing, to receive it in a machine-readable format and to
object to processing based on legitimate interest. To use these rights,
write to {email}. We answer within one month.</p>
<p>You also have the right to complain to a data protection supervisory
authority, in particular in the EU country where you live or work. In the
Czech Republic this is the
<a href="https://uoou.gov.cz">Úřad pro ochranu osobních údajů</a>.</p>

<h2>8. Security</h2>
<p>Connections are encrypted (HTTPS). Passwords are stored only as hashes.
Repeated failed sign-ins lock the account for 15 minutes. Organizations can
register batteries only after an MCBI administrator has approved them.</p>

<h2>9. Changes</h2>
<p>We will update this policy when the portal changes. The version date is
shown at the top. If a change affects what you agreed to, we will ask you to
accept it again.</p>
""",

        "terms_title": "Terms of use",
        "terms": """
<p>These terms apply to the MCBI EPR pilot portal (passport.mcbis.org),
operated by {company} ("MCBI"). By creating an organization account you accept
these terms and the <a href="/privacy?lang=en">privacy policy</a>.</p>

<h2>1. A pilot service</h2>
<p>The portal is a pilot prototype for testing battery registration, QR
labels and battery passport records. It is provided free of charge. Features
may change, be interrupted or be removed. Where MCBI and an organization sign
a separate pilot agreement, that agreement takes precedence over these terms.</p>

<h2>2. Who may use it</h2>
<p>Accounts are for organizations, not for private persons. The person who
creates an account confirms that they may act for the organization. MCBI may
approve or refuse an account request.</p>

<h2>3. Your account</h2>
<p>Keep your password secret and do not share your account. Tell us at
{email} straight away if you think someone else has used it.</p>

<h2>4. Your data</h2>
<ul>
<li>The battery data you enter remains yours. You give MCBI the right to
store, process and display it only as far as needed to run the portal.</li>
<li>The fields marked as public on a battery record can be seen by anyone who
scans its QR code or knows its ID. Do not enter confidential information in
public fields.</li>
<li>You are responsible for the data you enter being correct and for having
the right to enter it.</li>
<li>Where battery records contain personal data, MCBI processes it on your
behalf under a data processing agreement, which we provide on request.</li>
<li>You can ask for an export of your organization's records at any time.</li>
</ul>

<h2>5. No guarantee of legal compliance</h2>
<p>The portal follows the structure of the EU Battery Regulation
(EU) 2023/1542 and related standards as far as they are known today. Parts of
the detailed EU rules are still being finalised. Using the portal does not by
itself make your batteries compliant. The economic operator placing a battery
on the market stays responsible for meeting its legal obligations.</p>

<h2>6. Acceptable use</h2>
<p>Do not try to access data or accounts you are not allowed to access, do
not overload or attack the service, and do not enter unlawful content. MCBI
may suspend an account that breaks these rules.</p>

<h2>7. Availability and liability</h2>
<p>As a free pilot, the portal is provided "as is", without a promise of
availability. To the extent the law allows, MCBI is not liable for indirect
damage or lost data. This does not limit liability for intent or gross
negligence, or any liability that cannot be excluded by law. Keep your own
copies of important data.</p>

<h2>8. Ending use</h2>
<p>You can close your account at any time by writing to {email}. MCBI can end
the pilot with 30 days' notice by e-mail. Before an account is closed you can
request an export of your records.</p>

<h2>9. Changes and law</h2>
<p>We will tell account holders about important changes to these terms by
e-mail before they take effect. These terms are governed by Czech law, unless
a separate pilot agreement says otherwise.</p>
""",

        "impressum_title": "Legal notice",
        "impressum": """
<table>
<tr><th>Operator</th><td>{company}</td></tr>
<tr><th>Registered address</th><td>{address}</td></tr>
<tr><th>Registration number</th><td>{reg_no}</td></tr>
<tr><th>Represented by</th><td>{rep}</td></tr>
<tr><th>E-mail</th><td>{email}</td></tr>
<tr><th>Website</th><td><a href="https://mcbis.org">mcbis.org</a></td></tr>
</table>
<p>The portal is a pilot prototype. It does not sell goods or services and
does not collect payments.</p>
""",
    },

    "mn": {
        "nav_privacy": "Нууцлалын бодлого",
        "nav_terms": "Үйлчилгээний нөхцөл",
        "nav_impressum": "Хууль ёсны мэдээлэл",
        "nav_portal": "Портал руу буцах",
        "other_lang": "English",
        "draft": "Төсөл. Энэ хуудсыг гүйцээж байгаа бөгөөд хуульчаар хараахан "
                 "хянуулаагүй байна.",
        "updated": "Хувилбар {version}",

        "privacy_title": "Нууцлалын бодлого",
        "privacy": """
<p>Энэхүү бодлого нь MCBI EPR туршилтын портал (passport.mcbis.org) ямар хувийн
мэдээллийг, ямар зорилгоор боловсруулдаг, мөн та ямар эрхтэй болохыг
тайлбарлана. Портал нь туршилтын хувилбар бөгөөд батарейн бүртгэл, батарейн
паспортын системийг туршихад ашиглагддаг, төлбөр авдаггүй.</p>

<h2>1. Хариуцагч</h2>
<p>{company}<br>{address}<br>Бүртгэлийн дугаар: {reg_no}<br>
Имэйл: {email}</p>
<p>Бид мэдээлэл хамгаалах ажилтан томилоогүй. Нууцлалтай холбоотой бүх
асуултаа дээрх имэйл хаягаар илгээнэ үү.</p>

<h2>2. Хоёр өөр үүрэг</h2>
<ul>
<li><strong>Байгууллагын бүртгэл.</strong> Таны байгууллагын бүртгэлийг
ажиллуулахад шаардлагатай мэдээллийн хувьд MCBI мэдээллийг хэрхэн ашиглахыг
шийддэг тул <em>хариуцагч</em> (controller) болно.</li>
<li><strong>Батарейн бүртгэл.</strong> Батарейг байгууллагууд бүртгэдэг. Эдгээр
бүртгэлийн хувьд MCBI нь бүртгэсэн байгууллагын нэрийн өмнөөс мэдээлэл
боловсруулдаг тул түүний <em>боловсруулагч</em> (processor) болно. Батарейн
ихэнх мэдээлэл техникийн шинжтэй бөгөөд хувийн мэдээлэл биш. Хэрэв бүртгэлд
хувийн мэдээлэл агуулагдвал (жишээ нь хувиараа хөдөлмөр эрхлэгчийн холбоо
барих хаяг) бүртгэсэн байгууллага нь хариуцагч болох бөгөөд мэдээлэл
боловсруулах гэрээ хэрэглэгдэнэ.</li>
</ul>

<h2>3. Бидний боловсруулдаг мэдээлэл</h2>
<table>
<tr><th>Мэдээлэл</th><th>Зорилго</th><th>Хууль зүйн үндэслэл (GDPR)</th></tr>
<tr><td>Байгууллагын нэр, имэйл хаяг, байгууллагын төрөл, улс, бүртгүүлсэн
огноо</td><td>Таны бүртгэлийг үүсгэж ажиллуулах, байгууллагыг зөвшөөрөх,
туршилтын талаар тантай холбогдох</td><td>6(1)(b) зүйл: гэрээ</td></tr>
<tr><td>Нууц үг</td><td>Нэвтрэх. Бид нууц үгийг өөрийг нь биш, зөвхөн нэг
чиглэлтэй хэш (PBKDF2-SHA256) хэлбэрээр хадгалдаг.</td><td>6(1)(b) зүйл:
гэрээ</td></tr>
<tr><td>Таны зөвшөөрсөн нөхцөлийн огноо, хувилбар</td><td>Нөхцөл болон энэ
бодлогыг зөвшөөрснийг нотлох</td><td>6(1)(c) ба (f) зүйл: хуулийн үүрэг,
хууль ёсны ашиг сонирхол</td></tr>
<tr><td>Амжилтгүй нэвтрэх оролдлого (имэйл хаяг, цаг)</td><td>Нууц үг таах
оролдлогоос бүртгэлийг хамгаалах. Ажлын санах ойд хамгийн ихдээ 15 минут
хадгалагдах бөгөөд сервер дахин асахад устдаг.</td><td>6(1)(f) зүйл:
аюулгүй байдлын хууль ёсны ашиг сонирхол</td></tr>
<tr><td>Хостинг үйлчилгээ үзүүлэгчийн серверийн бүртгэл дэх техникийн
мэдээлэл (IP хаяг, цаг, хүссэн хуудас, хөтчийн төрөл)</td><td>Үйлчилгээг
ажиллуулах, алдаа илрүүлэх, буруугаар ашиглахаас сэргийлэх</td><td>6(1)(f)
зүйл: аюулгүй, хэвийн ажилладаг үйлчилгээний хууль ёсны ашиг сонирхол</td></tr>
<tr><td>Батарейн бүртгэл ба түүний түүх</td><td>Бүртгэсэн байгууллагад
батарейн бүртгэл, паспортын үйлчилгээ үзүүлэх</td><td>Бүртгэсэн байгууллагын
нэрийн өмнөөс (28-р зүйл)</td></tr>
</table>
<p>Зөвхөн QR код уншуулж эсвэл батарей хайж байгаа зочинд бүртгэл хэрэггүй.
Тэд бүртгэлийн зөвхөн нийтийн талбаруудыг харна.</p>

<h2>4. Күүки ба хяналт</h2>
<p>Портал нь зар сурталчилгаа, статистик эсвэл хянах күүки ашигладаггүй,
мөн гадны вэб фонт ашигладаггүй. Зөвхөн хуудасны сессийг нээлттэй байлгах
гэх мэт програм ажиллахад шаардлагатай техникийн хадгалалтыг ашигладаг.
Gradio системийн ашиглалтын статистикийг унтраасан.</p>

<h2>5. Мэдээллийг хаана хадгалж, хэнд дамжуулдаг вэ</h2>
<p>Портал болон түүний мэдээллийн санг Render Services, Inc. (525 Brannan St,
San Francisco, CA 94131, АНУ) компани <strong>{region}</strong> бүсэд
байршуулдаг. Render нь манай нэрийн өмнөөс өөрийн
<a href="https://render.com/dpa">Data Processing Addendum</a> гэрээний дагуу
мэдээлэл боловсруулдаг. Render нь АНУ-ын компани тул ЕХ-ноос гадна хандах
магадлалыг үгүйсгэх боломжгүй. Ийм шилжүүлгийн хувьд уг гэрээ нь ЕХ-АНУ-ын
Data Privacy Framework-д, түүнийг ашиглах боломжгүй үед ЕХ-ны Стандарт
гэрээний заалтад (SCC) тулгуурладаг. Render-ийн туслан гүйцэтгэгчдийн
жагсаалт түүний <a href="https://render.com/trust">trust хуудсанд</a> бий.</p>
<p>mcbis.org домэйны DNS-ийг Hostinger удирддаг. DNS нь зөвхөн хөтчийг сервер
рүү чиглүүлдэг бөгөөд Hostinger порталын агуулгыг хүлээн авдаггүй.</p>
<p>Бид хувийн мэдээллийг худалддаггүй бөгөөд хуулиар шаардсанаас бусад
тохиолдолд өөр хэнд ч дамжуулдаггүй.</p>

<h2>6. Мэдээллийг хэр удаан хадгалах вэ</h2>
<ul>
<li>Бүртгэлийн мэдээлэл: бүртгэл байгаа хугацаанд. Та бүртгэлээ хаахыг
хүссэний дараа хуулиар удаан хадгалах шаардлагагүй бол 30 хоногийн дотор
устгана.</li>
<li>Амжилтгүй нэвтрэх оролдлого: хамгийн ихдээ 15 минут.</li>
<li>Серверийн бүртгэл: хостинг үйлчилгээ үзүүлэгчийн стандарт тохиргоогоор
хадгалах хугацаанд.</li>
<li>Батарейн бүртгэл: бүртгэсэн байгууллагатай тохиролцсоны дагуу. ЕХ-ны
Батарейн журам (EU) 2023/1542-оор батарейн паспорт нь батарейн насан туршид
хүртээмжтэй байх ёстой тул паспортын мэдээллийг бүртгэлээс удаан хадгалах
шаардлага гарч болно.</li>
</ul>

<h2>7. Таны эрх</h2>
<p>Та өөрийн мэдээллийг үзэх, засуулах эсвэл устгуулах, боловсруулалтыг
хязгаарлах, машин уншихуйц хэлбэрээр авах, мөн хууль ёсны ашиг сонирхолд
үндэслэсэн боловсруулалтыг эсэргүүцэх эрхтэй. Эдгээр эрхээ эдлэхийн тулд
{email} хаягаар бичнэ үү. Бид нэг сарын дотор хариулна.</p>
<p>Мөн та мэдээлэл хамгаалах хяналтын байгууллагад, ялангуяа таны амьдарч
эсвэл ажилладаг ЕХ-ны улсын байгууллагад гомдол гаргах эрхтэй. Чех улсад
энэ нь <a href="https://uoou.gov.cz">Úřad pro ochranu osobních údajů</a>
(Хувийн мэдээлэл хамгаалах газар) юм.</p>

<h2>8. Аюулгүй байдал</h2>
<p>Холболт шифрлэгдсэн (HTTPS). Нууц үгийг зөвхөн хэш хэлбэрээр хадгалдаг.
Олон удаа буруу нэвтрэх оролдлого хийвэл бүртгэл 15 минут түгжигддэг.
Байгууллагууд MCBI-ийн админ зөвшөөрсний дараа л батарей бүртгэх
боломжтой.</p>

<h2>9. Өөрчлөлт</h2>
<p>Портал өөрчлөгдөхөд бид энэ бодлогыг шинэчилнэ. Хувилбарын огноо дээд
хэсэгт харагдана. Хэрэв өөрчлөлт таны зөвшөөрсөн зүйлд нөлөөлбөл бид танаас
дахин зөвшөөрөл авна.</p>
""",

        "terms_title": "Үйлчилгээний нөхцөл",
        "terms": """
<p>Эдгээр нөхцөл нь {company} ("MCBI")-ийн ажиллуулдаг MCBI EPR туршилтын
порталд (passport.mcbis.org) хамаарна. Байгууллагын бүртгэл үүсгэснээр та
эдгээр нөхцөл болон <a href="/privacy?lang=mn">нууцлалын бодлогыг</a>
зөвшөөрч байна.</p>

<h2>1. Туршилтын үйлчилгээ</h2>
<p>Портал нь батарейн бүртгэл, QR шошго, батарейн паспортын бүртгэлийг
туршихад зориулсан туршилтын прототип юм. Үнэ төлбөргүй үзүүлдэг. Боломжууд
өөрчлөгдөх, тасалдах эсвэл хасагдаж болно. Хэрэв MCBI болон байгууллага
тусдаа туршилтын гэрээ байгуулбал тэр гэрээ эдгээр нөхцөлөөс давуу хүчинтэй
байна.</p>

<h2>2. Хэн ашиглаж болох вэ</h2>
<p>Бүртгэл нь хувь хүнд биш, байгууллагад зориулагдсан. Бүртгэл үүсгэж буй
хүн байгууллагын нэрийн өмнөөс ажиллах эрхтэй гэдгээ баталж байна. MCBI
бүртгэлийн хүсэлтийг зөвшөөрөх эсвэл татгалзаж болно.</p>

<h2>3. Таны бүртгэл</h2>
<p>Нууц үгээ нууцалж, бүртгэлээ бусадтай хуваалцахгүй байна уу. Өөр хэн
нэгэн ашигласан гэж сэжиглэвэл {email} хаягаар даруй мэдэгдэнэ үү.</p>

<h2>4. Таны мэдээлэл</h2>
<ul>
<li>Таны оруулсан батарейн мэдээлэл таных хэвээр байна. Та MCBI-д зөвхөн
порталыг ажиллуулахад шаардлагатай хэмжээгээр хадгалах, боловсруулах,
харуулах эрх олгож байна.</li>
<li>Батарейн бүртгэлд нийтийн гэж тэмдэглэсэн талбаруудыг QR кодыг нь
уншуулсан эсвэл ID-г нь мэдэх хэн ч харж болно. Нийтийн талбарт нууц
мэдээлэл бүү оруулаарай.</li>
<li>Та өөрийн оруулсан мэдээлэл зөв байх, мөн түүнийг оруулах эрхтэй байх
үүрэгтэй.</li>
<li>Батарейн бүртгэлд хувийн мэдээлэл агуулагдвал MCBI түүнийг мэдээлэл
боловсруулах гэрээний дагуу таны нэрийн өмнөөс боловсруулна. Энэ гэрээг
хүсэлтээр өгнө.</li>
<li>Та хүссэн үедээ байгууллагынхаа бүртгэлийг экспортлон авахыг хүсч
болно.</li>
</ul>

<h2>5. Хуульд нийцэх баталгаа өгөхгүй</h2>
<p>Портал нь ЕХ-ны Батарейн журам (EU) 2023/1542 болон холбогдох стандартуудын
бүтцийг өнөөдрийн мэдэгдэж буй хэмжээгээр дагаж мөрддөг. ЕХ-ны нарийвчилсан
дүрмийн зарим хэсгийг одоо ч эцэслэж байна. Порталыг ашигласнаар таны
батарей өөрөө аяндаа шаардлага хангасан болохгүй. Батарейг зах зээлд
нийлүүлж буй эдийн засгийн оператор хуулийн үүргээ биелүүлэх хариуцлагатай
хэвээр байна.</p>

<h2>6. Зөвшөөрөгдөх хэрэглээ</h2>
<p>Танд хандах эрхгүй мэдээлэл, бүртгэлд хандахыг оролдох, үйлчилгээг хэт
ачаалах, халдах, мөн хууль бус агуулга оруулахыг хориглоно. Эдгээр дүрмийг
зөрчсөн бүртгэлийг MCBI түр зогсоож болно.</p>

<h2>7. Хүртээмж ба хариуцлага</h2>
<p>Үнэгүй туршилтын үйлчилгээ учир портал ямар ч ажиллагааны баталгаагүйгээр
"байгаа байдлаараа" үзүүлэгдэнэ. Хуулиар зөвшөөрөгдөх хэмжээнд MCBI шууд
бус хохирол эсвэл алдагдсан мэдээллийг хариуцахгүй. Энэ нь санаатай болон
ноцтой хайхрамжгүй үйлдлийн хариуцлага, мөн хуулиар хасах боломжгүй аливаа
хариуцлагыг хязгаарлахгүй. Чухал мэдээллийнхээ хуулбарыг өөртөө
хадгалаарай.</p>

<h2>8. Ашиглалтыг дуусгах</h2>
<p>Та {email} хаягаар бичиж хүссэн үедээ бүртгэлээ хааж болно. MCBI туршилтыг
30 хоногийн өмнө имэйлээр мэдэгдэж дуусгаж болно. Бүртгэл хаагдахаас өмнө
та бүртгэлүүдээ экспортлон авахыг хүсч болно.</p>

<h2>9. Өөрчлөлт ба хууль</h2>
<p>Эдгээр нөхцөлийн чухал өөрчлөлтийг хүчин төгөлдөр болохоос өмнө бүртгэл
эзэмшигчдэд имэйлээр мэдэгдэнэ. Тусдаа туршилтын гэрээнд өөрөөр заагаагүй
бол эдгээр нөхцөлд Чех улсын хууль үйлчилнэ.</p>
""",

        "impressum_title": "Хууль ёсны мэдээлэл",
        "impressum": """
<table>
<tr><th>Ажиллуулагч</th><td>{company}</td></tr>
<tr><th>Бүртгэлтэй хаяг</th><td>{address}</td></tr>
<tr><th>Бүртгэлийн дугаар</th><td>{reg_no}</td></tr>
<tr><th>Төлөөлөгч</th><td>{rep}</td></tr>
<tr><th>Имэйл</th><td>{email}</td></tr>
<tr><th>Вэбсайт</th><td><a href="https://mcbis.org">mcbis.org</a></td></tr>
</table>
<p>Портал нь туршилтын прототип юм. Бараа, үйлчилгээ худалддаггүй бөгөөд
төлбөр авдаггүй.</p>
""",
    },
}

STYLE = """
:root { --ink:#15201F; --quiet:#55615F; --line:#D9DEDC; --navy:#0D2253;
  --bg:#FFFFFF; --warn-bg:#FFF4E0; --warn:#7A4A00; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#E9EEEC; --quiet:#A9B3B0; --line:#33403D; --navy:#9AA8CC;
    --bg:#111716; --warn-bg:#3A2A0A; --warn:#F3C77A; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 24px 16px 64px; }
nav { display:flex; flex-wrap:wrap; gap:8px 16px; font-size:14px;
  padding-bottom:12px; border-bottom:1px solid var(--line); }
nav a { color:var(--navy); }
nav a[aria-current] { font-weight:700; text-decoration:none; color:var(--ink); }
h1 { font-size: 28px; margin: 24px 0 4px; }
h2 { font-size: 19px; margin: 28px 0 8px; }
.version { color:var(--quiet); font-size:14px; margin:0 0 16px; }
.draft { background:var(--warn-bg); color:var(--warn); border-radius:8px;
  padding:10px 14px; margin:16px 0; font-size:14px; }
.missing { color:var(--warn); font-weight:600; }
a { color:var(--navy); }
table { width:100%; border-collapse:collapse; margin:12px 0; font-size:15px; }
th, td { text-align:left; vertical-align:top; padding:8px;
  border-bottom:1px solid var(--line); }
th { font-weight:600; }
@media (max-width: 560px) { table, tbody, tr, th, td { display:block; }
  tr { border-bottom:1px solid var(--line); padding:6px 0; }
  th, td { border:0; padding:2px 0; } }
"""


def render_page(page, lang):
    """Return the full HTML document for one legal page."""
    lang = lang if lang in TEXTS else "en"
    page = page if page in PAGES else "privacy"
    text = TEXTS[lang]
    fields = _fields(lang)
    other = "mn" if lang == "en" else "en"
    links = []
    for name in PAGES:
        current = ' aria-current="page"' if name == page else ""
        links.append(f'<a href="/{name}?lang={lang}"{current}>'
                     f'{text["nav_" + name]}</a>')
    links.append(f'<a href="/?lang={lang}">{text["nav_portal"]}</a>')
    links.append(f'<a href="/{page}?lang={other}" lang="{other}">'
                 f'{text["other_lang"]}</a>')
    draft = "" if is_final() else f'<p class="draft">{text["draft"]}</p>'
    body = text[page].format(**fields)
    title = text[page + "_title"]
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · MCBI EPR Portal</title>
<style>{STYLE}</style>
</head>
<body><main>
<nav>{''.join(links)}</nav>
<h1>{title}</h1>
<p class="version">{text["updated"].format(**fields)}</p>
{draft}
{body}
</main></body></html>"""
