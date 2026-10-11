"""Уроки грамматики. Порядок уроков = рекомендуемый путь от A2 к B1.

Каждый урок: короткая теория + практика.
Типы вопросов:
  choice — выбрать вариант (answer — индекс правильного);
  text   — написать ответ (answers — все допустимые варианты).

Чтобы добавить урок, допиши новый Lesson в LESSONS. id урока не меняй после
запуска бота — по нему хранится прогресс.
"""
from dataclasses import dataclass, field


@dataclass
class Question:
    kind: str  # "choice" | "text"
    prompt: str
    explain: str
    options: list[str] = field(default_factory=list)
    answer: int = 0
    answers: list[str] = field(default_factory=list)


def choice(prompt: str, options: list[str], answer: int, explain: str) -> Question:
    return Question("choice", prompt, explain, options=options, answer=answer)


def text(prompt: str, answers: list[str], explain: str) -> Question:
    return Question("text", prompt, explain, answers=answers)


@dataclass
class Lesson:
    id: str
    title: str
    weak_spot: str  # к какому слабому месту из теста относится
    theory: str
    questions: list[Question]


LESSONS: list[Lesson] = [
    Lesson(
        id="present_simple",
        title="⏰ Present Simple: he goes, she doesn't",
        weak_spot="verbs",
        theory=(
            "<b>Present Simple</b> — то, что происходит регулярно: привычки, факты, расписание.\n\n"
            "Главная ловушка — <b>he / she / it</b>: к глаголу добавляем <b>-s</b> 🐍\n"
            "I work → She work<b>s</b>\n"
            "I go → He go<b>es</b> (после o, s, sh, ch, x → <b>-es</b>: watches, fixes)\n"
            "I study → She stud<b>ies</b>\n"
            "have → ha<b>s</b>\n\n"
            "Отрицание и вопрос — через <b>do / does</b>, и тогда <b>-s</b> у глагола пропадает:\n"
            "She <b>doesn't</b> go. <b>Does</b> she go?\n\n"
            "💡 В тесте было <i>She ___ to work by bus</i> → ты выбрал <i>going</i>. "
            "Правильно <b>goes</b>: every day = привычка = Present Simple."
        ),
        questions=[
            choice("She ___ to work by bus every day.", ["go", "goes", "going"], 1,
                   "she + глагол + s → goes. Every day = регулярно."),
            choice("My brother ___ series every evening.", ["watch", "watchs", "watches"], 2,
                   "После ch добавляем -es: watches."),
            choice("___ he speak English?", ["Do", "Does", "Is"], 1,
                   "he/she/it → Does. Глагол после does — без -s."),
            choice("She doesn't ___ coffee.", ["like", "likes", "liking"], 0,
                   "После doesn't глагол в начальной форме: doesn't like."),
            choice("We usually ___ dinner at 7.", ["have", "has", "having"], 0,
                   "we → без -s: have."),
            text("Переведи: Он живёт в маленьком городе.",
                 ["he lives in a small town", "he lives in a small city"],
                 "He live<b>s</b> in <b>a</b> small town. -s у глагола + артикль a."),
            text("Переведи: Она не смотрит телевизор.",
                 ["she does not watch tv", "she doesn't watch tv", "she does not watch television",
                  "she doesn't watch television", "she does not watch the tv", "she doesn't watch the tv"],
                 "She <b>doesn't watch</b> TV. Отрицание через doesn't, глагол без -s."),
            text("Поставь глагол в нужную форму: My friend (study) ___ Japanese.",
                 ["studies"], "y после согласной → ies: studies."),
        ],
    ),
    Lesson(
        id="present_continuous",
        title="🎬 Present Continuous: I'm watching right now",
        weak_spot="verbs",
        theory=(
            "<b>Present Continuous</b> = am/is/are + глагол<b>-ing</b>. Действие прямо сейчас или в этот период.\n\n"
            "I <b>am watching</b> a series now.\n"
            "She <b>is going</b> to work (сейчас, в данный момент).\n"
            "They <b>aren't sleeping</b>.\n\n"
            "⚖️ Сравни:\n"
            "She <b>goes</b> to work by bus every day (привычка)\n"
            "She <b>is going</b> to work right now (сейчас)\n\n"
            "Маркеры: now, right now, at the moment, today, these days, Look!, Listen!\n\n"
            "⚠️ Без am/is/are нельзя: ❌ <i>I watching</i> → ✅ I'm watching.\n"
            "⚠️ Глаголы чувств и мыслей обычно не ставят в -ing: know, like, want, understand."
        ),
        questions=[
            choice("Look! It ___.", ["rains", "is raining", "raining"], 1,
                   "Look! = прямо сейчас → is raining."),
            choice("I ___ to music every day.", ["listen", "am listening", "listening"], 0,
                   "every day = привычка → Present Simple."),
            choice("Shh! The baby ___.", ["sleeps", "is sleeping", "sleep"], 1,
                   "Прямо сейчас → is sleeping."),
            choice("I ___ what you mean.", ["understand", "am understanding", "understanding"], 0,
                   "understand — глагол состояния, в -ing обычно не ставится."),
            choice("What ___ you doing now?", ["do", "are", "is"], 1,
                   "you → are: What are you doing?"),
            text("Переведи: Я сейчас смотрю сериал.",
                 ["i am watching a series now", "i'm watching a series now", "i am watching a series right now",
                  "i'm watching a series right now", "now i am watching a series", "i am watching a show now",
                  "i'm watching a show now", "i am now watching a series"],
                 "I <b>am watching</b> a series now."),
            text("Поставь глагол: They (play) ___ football at the moment.",
                 ["are playing"], "they → are + playing."),
        ],
    ),
    Lesson(
        id="past_simple_regular",
        title="⏪ Past Simple: worked, didn't work",
        weak_spot="verbs",
        theory=(
            "<b>Past Simple</b> — законченное действие в прошлом: yesterday, last week, in 2020, ago.\n\n"
            "Правильные глаголы: + <b>-ed</b>\n"
            "watch → watch<b>ed</b>, start → start<b>ed</b>, stop → stop<b>ped</b>, study → stud<b>ied</b>\n\n"
            "Отрицание и вопрос — через <b>did</b>, и глагол возвращается в начальную форму:\n"
            "I <b>didn't watch</b> it. <b>Did</b> you <b>watch</b> it?\n"
            "❌ <i>I didn't watched</i> — двойное прошедшее, так нельзя.\n\n"
            "💡 В тесте: <i>he is change his opinion</i> → правильно <b>he changed</b> his opinion."
        ),
        questions=[
            choice("Yesterday I ___ a new series.", ["start", "started", "starting"], 1,
                   "yesterday → Past Simple: started."),
            choice("She ___ her opinion after a month.", ["is change", "changed", "changes"], 1,
                   "Законченное действие в прошлом → changed."),
            choice("I didn't ___ the film.", ["like", "liked", "liking"], 0,
                   "После didn't — начальная форма: didn't like."),
            choice("___ you watch the match last night?", ["Do", "Did", "Were"], 1,
                   "last night → Did."),
            choice("We ___ in a hotel for three nights.", ["stayed", "stay", "were stay"], 0,
                   "stay → stayed."),
            text("Поставь в Past Simple: I (stop) ___ watching it after episode 2.",
                 ["stopped"], "Короткий глагол на согласную: stop → sto<b>pp</b>ed."),
            text("Переведи: Я не позвонил ему вчера.",
                 ["i did not call him yesterday", "i didn't call him yesterday",
                  "yesterday i did not call him", "yesterday i didn't call him"],
                 "I <b>didn't call</b> him yesterday."),
        ],
    ),
    Lesson(
        id="past_simple_irregular",
        title="⚡ Неправильные глаголы: went, forgot, got",
        weak_spot="verbs",
        theory=(
            "Около 100 частых глаголов образуют прошедшее время не через -ed, их надо просто запомнить. "
            "Они уже лежат у тебя в словах (тема ⚡) и будут крутиться в повторении.\n\n"
            "Топ для разговора:\n"
            "go → <b>went</b> · get → <b>got</b> · forget → <b>forgot</b>\n"
            "leave → <b>left</b> · take → <b>took</b> · see → <b>saw</b>\n"
            "buy → <b>bought</b> · think → <b>thought</b> · be → <b>was/were</b>\n\n"
            "💡 Вопрос 5 из теста: <i>Вчера я забыл взять зонтик, поэтому промок под дождём.</i>\n"
            "→ Yesterday I <b>forgot</b> to take my umbrella, so I <b>got wet</b> in the rain.\n\n"
            "💡 «Где я родился» — <b>where I was born</b> (не <i>where I am was born</i>)."
        ),
        questions=[
            choice("Last weekend I ___ to the cinema.", ["goed", "went", "gone"], 1, "go → went."),
            choice("Yesterday I ___ my umbrella.", ["forget", "forgot", "forgetted"], 1, "forget → forgot."),
            choice("I ___ wet in the rain.", ["got", "get", "getted"], 0, "get → got. get wet = промокнуть."),
            choice("We ___ early because the film was boring.", ["leaved", "left", "leave"], 1, "leave → left."),
            choice("I was ___ in Russia.", ["born", "borned", "bear"], 0, "Родиться = be born: I was born."),
            text("Past Simple от buy:", ["bought"], "buy → <b>bought</b>."),
            text("Past Simple от think:", ["thought"], "think → <b>thought</b>."),
            text("Переведи: Вчера я забыл взять зонтик, поэтому промок.",
                 ["yesterday i forgot to take my umbrella so i got wet",
                  "yesterday i forgot to take an umbrella so i got wet",
                  "i forgot to take my umbrella yesterday so i got wet",
                  "i forgot to take an umbrella yesterday so i got wet",
                  "yesterday i forgot my umbrella so i got wet",
                  "yesterday i forgot to take my umbrella so i got wet in the rain",
                  "yesterday i forgot to take an umbrella so i got wet in the rain"],
                 "Yesterday I <b>forgot</b> to take my umbrella, so I <b>got wet</b>."),
        ],
    ),
    Lesson(
        id="verb_ing",
        title="🔗 start watching, used to think",
        weak_spot="verbs",
        theory=(
            "После некоторых глаголов второй глагол идёт с <b>-ing</b>:\n"
            "start / stop / finish / enjoy / like / love / hate / keep / mind\n"
            "I started <b>watching</b> series. Stop <b>talking</b>! I enjoy <b>travelling</b>.\n\n"
            "После других — с <b>to</b>:\n"
            "want / decide / plan / hope / forget / need / would like\n"
            "I want <b>to travel</b>. I forgot <b>to take</b> my umbrella.\n\n"
            "💡 В тесте: <i>he started watch</i> → правильно <b>started watching</b>.\n\n"
            "<b>used to</b> + глагол = раньше (а теперь нет):\n"
            "I <b>used to think</b> it was impossible. Раньше я думал, что это невозможно."
        ),
        questions=[
            choice("I started ___ series with subtitles.", ["watch", "watching", "watched"], 1,
                   "start + -ing: started watching."),
            choice("I want ___ to Japan.", ["travel", "travelling", "to travel"], 2, "want + to."),
            choice("Stop ___ ! I'm trying to sleep.", ["talk", "talking", "to talking"], 1, "stop + -ing."),
            choice("I ___ think English was impossible.", ["use to", "used to", "was used"], 1,
                   "used to + глагол = раньше."),
            choice("I enjoy ___ new words.", ["learning", "to learn", "learn"], 0, "enjoy + -ing."),
            choice("I forgot ___ my passport!", ["take", "taking", "to take"], 2,
                   "forget to do = забыть сделать."),
            text("Переведи: Я начал учить английский.",
                 ["i started learning english", "i started to learn english", "i began learning english",
                  "i began to learn english", "i have started learning english"],
                 "I started <b>learning</b> English (можно и started to learn)."),
            text("Переведи: Раньше я жил в Москве.",
                 ["i used to live in moscow"], "I <b>used to live</b> in Moscow."),
        ],
    ),
    Lesson(
        id="present_perfect",
        title="✅ Present Perfect: I've never been to Japan",
        weak_spot="verbs",
        theory=(
            "<b>have / has + 3-я форма</b> (worked, been, seen, done).\n"
            "Важен <b>результат или опыт</b>, а не когда именно это было.\n\n"
            "Опыт: I've <b>never been</b> to Japan. Have you <b>ever tried</b> sushi?\n"
            "Результат: I've <b>lost</b> my keys (и сейчас их нет).\n"
            "already / yet / just: I've <b>already</b> seen it. Have you finished <b>yet</b>?\n"
            "for / since: I've lived here <b>for</b> 5 years / <b>since</b> 2020.\n\n"
            "⚖️ Есть точное время в прошлом (yesterday, in 2019, last week) → Past Simple:\n"
            "I <b>went</b> to Kazan last year. НО: I <b>have been</b> to Kazan.\n\n"
            "💡 Из теста: <i>now I was only in Russia</i> → So far I <b>have only been</b> to Russia."
        ),
        questions=[
            choice("I ___ never been abroad.", ["have", "has", "was"], 0, "I → have + been."),
            choice("___ you ever tried sushi?", ["Did", "Have", "Do"], 1, "ever + опыт → Have you ever…?"),
            choice("She ___ already seen this episode.", ["have", "has", "is"], 1, "she → has."),
            choice("I ___ to Kazan last year.", ["have been", "went", "have gone"], 1,
                   "last year — точное время → Past Simple."),
            choice("I have lived here ___ 2020.", ["for", "since", "from"], 1,
                   "since + точка во времени, for + период."),
            choice("Have you finished ___?", ["already", "yet", "just"], 1, "yet — в вопросах и отрицаниях в конце."),
            text("Переведи: Я никогда не был в Японии.",
                 ["i have never been to japan", "i've never been to japan"],
                 "I <b>have never been to</b> Japan. Был где-то = have been <b>to</b>."),
            text("3-я форма глагола see:", ["seen"], "see – saw – <b>seen</b>."),
        ],
    ),
    Lesson(
        id="future",
        title="🔮 Будущее: will и going to",
        weak_spot="verbs",
        theory=(
            "<b>going to</b> — план, уже решил:\n"
            "I'm <b>going to</b> travel to Vietnam next summer.\n\n"
            "<b>will</b> — решение прямо сейчас, обещание, прогноз:\n"
            "I'm cold. I'<b>ll</b> close the window. I <b>will</b> help you. It <b>will</b> rain tomorrow.\n\n"
            "<b>Present Continuous</b> — договорённость с конкретным временем:\n"
            "I'm <b>meeting</b> Anna at 7.\n\n"
            "⚠️ После will — глагол без to: ❌ <i>will to go</i> → ✅ will go"
        ),
        questions=[
            choice("Look at the clouds! It ___ rain.", ["is going to", "will to", "goes to"], 0,
                   "Есть признак → going to."),
            choice("— The phone is ringing. — I ___ answer it!", ["am going to", "will", "answer"], 1,
                   "Решение в моменте → will."),
            choice("Next summer we ___ visit Japan. We've bought tickets!", ["will", "are going to", "go to"], 1,
                   "Уже решили и купили билеты → going to."),
            choice("I promise I ___ be late.", ["won't", "don't", "am not going"], 0, "Обещание → won't."),
            text("Переведи: Я собираюсь путешествовать по Азии.",
                 ["i am going to travel around asia", "i'm going to travel around asia",
                  "i am going to travel in asia", "i'm going to travel in asia", "i am going to travel to asia",
                  "i'm going to travel to asia", "i am going to travel across asia",
                  "i'm going to travel across asia"],
                 "I'm <b>going to travel around</b> Asia."),
            text("Переведи: Я помогу тебе.", ["i will help you", "i'll help you"], "I <b>will</b> help you."),
        ],
    ),
    Lesson(
        id="articles",
        title="🅰️ Артикли a / an / the",
        weak_spot="articles",
        theory=(
            "<b>a / an</b> — один, какой-то, впервые упоминаем (только с исчисляемыми в ед. ч.):\n"
            "I live in <b>a</b> small town. She is <b>an</b> actor. (an — перед гласным звуком)\n\n"
            "<b>the</b> — конкретный, понятно какой, уже упоминали, единственный:\n"
            "I saw <b>a</b> film. <b>The</b> film was boring.\n"
            "<b>the</b> sun, <b>the</b> best, <b>the</b> same, <b>the</b> cinema, <b>the</b> USA\n\n"
            "<b>Без артикля</b>: множественное и неисчисляемое в общем смысле, страны, города, языки, "
            "приёмы пищи: I like <b>coffee</b>. <b>Dogs</b> are cute. I live in <b>Russia</b>. I speak <b>English</b>.\n\n"
            "💡 Из теста: <i>I live in the small city</i> → I live in <b>a</b> small town "
            "(какой-то город, впервые упоминаем)."
        ),
        questions=[
            choice("I live in ___ small town.", ["a", "the", "—"], 0, "Впервые упоминаем, один из многих → a."),
            choice("She is ___ engineer.", ["a", "an", "the"], 1, "engineer начинается с гласного звука → an."),
            choice("I saw a film yesterday. ___ film was boring.", ["A", "The", "—"], 1,
                   "Уже упоминали → the."),
            choice("I would like to travel to ___ Japan.", ["the", "a", "—"], 2, "Страны — без артикля."),
            choice("This is ___ best day of my life!", ["a", "the", "—"], 1, "Превосходная степень → the best."),
            choice("I love ___ music.", ["the", "a", "—"], 2, "Музыка вообще → без артикля."),
            choice("Can you close ___ window, please?", ["a", "the", "—"], 1, "Понятно, какое окно → the."),
            text("Вставь артикль (a, an, the или -): I need ___ umbrella.", ["an"],
                 "umbrella начинается с гласного звука → <b>an</b>."),
        ],
    ),
    Lesson(
        id="plurals",
        title="👥 Множественное число: two people, many / much",
        weak_spot="articles",
        theory=(
            "Обычно + <b>-s / -es</b>: city → cit<b>ies</b>, bus → bus<b>es</b>.\n\n"
            "Исключения, которые встречаются постоянно:\n"
            "person → <b>people</b> · man → <b>men</b> · woman → <b>women</b> · child → <b>children</b>\n"
            "foot → <b>feet</b> · tooth → <b>teeth</b> · mouse → <b>mice</b>\n\n"
            "💡 Из теста: <i>a table for two person</i> → a table for two <b>people</b>.\n\n"
            "<b>many</b> — с исчисляемыми: many people, many countries\n"
            "<b>much</b> — с неисчисляемыми: much money, much time\n"
            "<b>a lot of</b> — с любыми.\n\n"
            "Неисчисляемые (без -s и без a): money, information, advice, news, luggage, furniture.\n"
            "⚠️ Заглавная буква только у имён и названий: countries, но Asian countries, Japan."
        ),
        questions=[
            choice("A table for two ___, please.", ["person", "persons", "people"], 2, "person → people."),
            choice("How ___ money do you have?", ["many", "much", "lot"], 1, "money неисчисляемое → much."),
            choice("How ___ countries have you visited?", ["many", "much", "lot"], 0, "countries → many."),
            choice("She has three ___.", ["childs", "children", "childrens"], 1, "child → children."),
            choice("Can you give me some ___?", ["advices", "advice", "an advice"], 1,
                   "advice неисчисляемое: some advice."),
            choice("My ___ is very heavy.", ["luggage", "luggages", "a luggage"], 0, "luggage неисчисляемое."),
            text("Множественное от woman:", ["women"], "woman → <b>women</b>."),
            text("Переведи: Я хочу заказать столик на двоих.",
                 ["i want to book a table for two", "i'd like to book a table for two",
                  "i would like to book a table for two", "i want to reserve a table for two",
                  "i would like to reserve a table for two", "i'd like to reserve a table for two",
                  "i want to book a table for two people", "i would like to book a table for two people",
                  "i'd like to book a table for two people"],
                 "I'd like to <b>book</b> a table for two (people). Столик бронируют — book/reserve, а не order."),
        ],
    ),
    Lesson(
        id="prepositions",
        title="📍 Предлоги: to, in, at, on",
        weak_spot="articles",
        theory=(
            "<b>Движение куда</b> → <b>to</b>: go <b>to</b> Japan, travel <b>to</b> Vietnam, come <b>to</b> me\n"
            "⚠️ Но: go home (без to).\n"
            "💡 Из теста: <i>travel in Vietnam</i> → travel <b>to</b> Vietnam (поехать туда). "
            "travel <b>in/around</b> Vietnam — путешествовать по стране, уже находясь там.\n\n"
            "<b>Место</b>:\n"
            "<b>in</b> — внутри, города и страны: in a small town, in Russia, in the car\n"
            "<b>at</b> — точка: at home, at work, at the airport, at the bus stop\n"
            "<b>on</b> — на поверхности: on the table, on the wall, on the bus/train\n\n"
            "<b>Время</b>:\n"
            "<b>at</b> + время: at 8 pm, at night, at the weekend\n"
            "<b>on</b> + день/дата: on Monday, on 5 May\n"
            "<b>in</b> + месяц/год/время суток: in May, in 2026, in the morning"
        ),
        questions=[
            choice("I'd like to travel ___ Vietnam.", ["in", "to", "at"], 1, "Куда → to."),
            choice("I live ___ a small town.", ["in", "at", "on"], 0, "Город → in."),
            choice("A table for two ___ 8 pm.", ["in", "on", "at"], 2, "Время по часам → at."),
            choice("See you ___ Monday!", ["in", "on", "at"], 1, "День недели → on."),
            choice("I was born ___ 2001.", ["in", "on", "at"], 0, "Год → in."),
            choice("I'm ___ the airport now.", ["in", "at", "to"], 1, "Точка, место-функция → at."),
            choice("Let's go ___!", ["to home", "home", "at home"], 1, "go home — без предлога."),
            text("Вставь предлог: I usually read ___ the morning.", ["in"], "in the morning."),
        ],
    ),
    Lesson(
        id="conditional_1",
        title="🌧 If + Present: If it rains, I'll stay home",
        weak_spot="conditionals",
        theory=(
            "<b>Реальное условие</b> в будущем (1-й тип):\n"
            "<b>If</b> + Present Simple, … <b>will</b> + глагол\n\n"
            "If it <b>rains</b>, I <b>will stay</b> at home.\n"
            "If you <b>study</b> every day, you <b>will reach</b> B1.\n\n"
            "⚠️ Главная ловушка: после <b>if</b> НЕ ставим will, даже если по-русски будущее!\n"
            "Если я <i>найду</i> работу… → If I <b>find</b> a job… (не <i>will find</i>)\n\n"
            "То же с <b>when, before, after, as soon as, unless</b>:\n"
            "I'll call you <b>when</b> I <b>arrive</b>."
        ),
        questions=[
            choice("If it ___ tomorrow, we'll stay home.", ["will rain", "rains", "rained"], 1,
                   "После if — Present Simple."),
            choice("If you study every day, you ___ B1.", ["reach", "will reach", "reached"], 1,
                   "Главная часть → will."),
            choice("I'll call you when I ___.", ["will arrive", "arrive", "arrived"], 1,
                   "После when — Present Simple."),
            choice("If she ___ late, we will start without her.", ["is", "will be", "was"], 0,
                   "После if — Present: is."),
            choice("We won't go ___ it's sunny.", ["if", "unless", "when"], 1, "unless = если не."),
            text("Переведи: Если я найду билеты, я поеду в Японию.",
                 ["if i find tickets i will go to japan", "if i find tickets i'll go to japan",
                  "if i find the tickets i will go to japan", "if i find the tickets i'll go to japan",
                  "if i find tickets i will travel to japan", "if i find tickets i'll travel to japan",
                  "i will go to japan if i find tickets", "i'll go to japan if i find tickets"],
                 "If I <b>find</b> tickets, I <b>will go</b> to Japan."),
        ],
    ),
    Lesson(
        id="conditional_2",
        title="💸 If I had…, I would… (мечты)",
        weak_spot="conditionals",
        theory=(
            "<b>Нереальное условие</b> сейчас / в будущем (2-й тип): мечты, фантазии, «если бы».\n"
            "<b>If</b> + Past Simple, … <b>would</b> + глагол\n\n"
            "If I <b>had</b> more money, I <b>would travel</b> around the world.\n"
            "(денег сейчас нет — это мечта)\n\n"
            "If I <b>were</b> you, I <b>would</b> watch it. (для всех лиц можно were)\n\n"
            "⚠️ Прошедшее время тут не про прошлое, а про «нереальность».\n"
            "💡 В тесте ты выбрал <i>If I will have more money</i> → правильно <b>If I had</b>.\n\n"
            "Формула-мем: <b>if + past → would + verb</b> 🧠"
        ),
        questions=[
            choice("If I ___ more money, I would travel around the world.", ["have", "had", "will have"], 1,
                   "Нереальное условие → if + Past: had."),
            choice("If I were rich, I ___ a house by the sea.", ["will buy", "would buy", "bought"], 1,
                   "Главная часть → would + глагол."),
            choice("If I ___ you, I would apologise.", ["am", "were", "will be"], 1, "If I were you — классика."),
            choice("What would you do if you ___ the lottery?", ["win", "won", "will win"], 1, "if + Past: won."),
            choice("If she spoke English, she ___ abroad.", ["would work", "will work", "works"], 0,
                   "would + глагол."),
            text("Переведи: Если бы у меня было больше времени, я бы учил японский.",
                 ["if i had more time i would learn japanese", "if i had more time i'd learn japanese",
                  "if i had more time i would study japanese", "if i had more time i'd study japanese",
                  "i would learn japanese if i had more time", "i would study japanese if i had more time"],
                 "If I <b>had</b> more time, I <b>would learn</b> Japanese."),
            text("Поставь глагол: If I (know) ___ his number, I would call him.", ["knew"],
                 "Нереальное условие → if + Past: <b>knew</b>."),
        ],
    ),
    Lesson(
        id="conditional_3",
        title="🕰 If I had known… (сожаления о прошлом)",
        weak_spot="conditionals",
        theory=(
            "<b>Нереальное условие в прошлом</b> (3-й тип): уже случилось, поменять нельзя.\n"
            "<b>If</b> + had + 3-я форма, … <b>would have</b> + 3-я форма\n\n"
            "If I <b>had known</b> about it earlier, I <b>wouldn't have gone</b> there.\n"
            "Если бы я знал об этом раньше, я бы туда не поехал.\n\n"
            "If we <b>had left</b> earlier, we <b>wouldn't have missed</b> the flight.\n\n"
            "💡 В тесте: <i>If I know it earler, i don't going there</i> → "
            "If I <b>had known</b> about it earlier, I <b>wouldn't have gone</b> there.\n\n"
            "Для B1 достаточно узнавать эту конструкцию и уметь собрать её по формуле. "
            "В речи: If I'd known… I wouldn't've gone…"
        ),
        questions=[
            choice("If I ___ about it earlier, I wouldn't have gone there.",
                   ["knew", "had known", "would know"], 1, "Прошлое нереальное → had known."),
            choice("If we had left earlier, we ___ the flight.",
                   ["wouldn't miss", "wouldn't have missed", "didn't miss"], 1, "would have + 3-я форма."),
            choice("She would have passed the exam if she ___ harder.",
                   ["had studied", "studied", "would study"], 0, "if + had + 3-я форма."),
            choice("Какой тип? «If I had money, I would buy it».", ["1-й", "2-й", "3-й"], 1,
                   "if + Past, would + глагол → 2-й (сейчас)."),
            choice("Какой тип? «If I had known, I would have come».", ["1-й", "2-й", "3-й"], 2,
                   "had known + would have come → 3-й (прошлое)."),
            text("Переведи: Если бы я знал об этом раньше, я бы не поехал туда.",
                 ["if i had known about it earlier i would not have gone there",
                  "if i had known about it earlier i wouldn't have gone there",
                  "if i'd known about it earlier i wouldn't have gone there",
                  "if i'd known about it earlier i would not have gone there",
                  "if i had known about this earlier i would not have gone there",
                  "if i had known about this earlier i wouldn't have gone there",
                  "if i had known it earlier i wouldn't have gone there",
                  "if i had known it earlier i would not have gone there",
                  "if i had known about it before i wouldn't have gone there",
                  "if i had known about it before i would not have gone there"],
                 "If I <b>had known</b> about it earlier, I <b>wouldn't have gone</b> there."),
        ],
    ),
    Lesson(
        id="comparatives",
        title="📈 Сравнения: bigger, more interesting, the best",
        weak_spot="other",
        theory=(
            "Короткие прилагательные: <b>-er / the -est</b>\n"
            "cheap → cheap<b>er</b> → the cheap<b>est</b>\n"
            "big → bi<b>gg</b>er · easy → eas<b>ier</b>\n\n"
            "Длинные: <b>more / the most</b>\n"
            "interesting → <b>more</b> interesting → <b>the most</b> interesting\n\n"
            "Исключения: good → <b>better</b> → <b>the best</b>; bad → <b>worse</b> → <b>the worst</b>; "
            "far → further\n\n"
            "Сравниваем через <b>than</b>: Japan is more expensive <b>than</b> Vietnam.\n"
            "Равенство: as … as: This show is <b>as good as</b> the book."
        ),
        questions=[
            choice("Vietnam is ___ than Japan.", ["cheap", "cheaper", "more cheap"], 1, "Короткое → cheaper."),
            choice("This is the ___ series I've ever seen.", ["better", "best", "most good"], 1,
                   "good → the best."),
            choice("English is ___ than Japanese.", ["easier", "more easy", "easyer"], 0, "easy → easier."),
            choice("The book is more interesting ___ the film.", ["that", "then", "than"], 2, "Сравнение → than."),
            choice("Today is ___ than yesterday.", ["bad", "worse", "badder"], 1, "bad → worse."),
            text("Сравнительная степень от expensive:", ["more expensive"], "Длинное слово → <b>more expensive</b>."),
        ],
    ),
    Lesson(
        id="modals",
        title="🛂 can, must, have to, should",
        weak_spot="other",
        theory=(
            "<b>can</b> — могу, умею: I <b>can</b> swim. <b>Can</b> I pay by card?\n"
            "<b>could</b> — мог (в прошлом) и вежливая просьба: <b>Could</b> you help me?\n"
            "<b>must</b> — должен (по моему мнению / правило): You <b>must</b> show your passport.\n"
            "<b>have to</b> — приходится (обстоятельства): I <b>have to</b> get up at 6.\n"
            "<b>should</b> — совет: You <b>should</b> watch this series!\n\n"
            "⚠️ После модальных — глагол без to: ❌ <i>can to go</i>, ❌ <i>should to watch</i>\n"
            "⚠️ <b>don't have to</b> = не обязательно; <b>mustn't</b> = нельзя!"
        ),
        questions=[
            choice("You ___ watch this series, it's amazing!", ["should", "must to", "have"], 0, "Совет → should."),
            choice("___ you help me with my luggage?", ["Could", "Must", "Should"], 0, "Вежливая просьба → Could."),
            choice("You ___ smoke on the plane. It's forbidden.", ["don't have to", "mustn't", "shouldn't to"], 1,
                   "Запрет → mustn't."),
            choice("It's Saturday, I ___ get up early.", ["mustn't", "don't have to", "can't"], 1,
                   "Не обязательно → don't have to."),
            choice("I can ___ English a little.", ["speak", "to speak", "speaking"], 0, "can + глагол без to."),
            text("Переведи: Можно оплатить картой?",
                 ["can i pay by card", "could i pay by card", "can i pay with a card", "could i pay with a card",
                  "can i pay with card", "may i pay by card"],
                 "<b>Can I pay by card?</b>"),
        ],
    ),
    Lesson(
        id="passive",
        title="🏯 Пассив: It was built in 1600",
        weak_spot="verbs",
        theory=(
            "Пассив — когда важно, что сделано, а не кто сделал.\n"
            "<b>be + 3-я форма</b>\n\n"
            "Present: Sushi <b>is made</b> with raw fish. English <b>is spoken</b> here.\n"
            "Past: The temple <b>was built</b> in 1600. I <b>was born</b> in Russia.\n\n"
            "Кто сделал — через <b>by</b>: The series <b>was directed by</b> Nolan.\n\n"
            "💡 Ты уже знаешь один пассив: <b>I was born</b> — «я был рождён»."
        ),
        questions=[
            choice("This temple ___ in 1600.", ["built", "was built", "is build"], 1, "Прошлое пассив → was built."),
            choice("English ___ all over the world.", ["speaks", "is spoken", "is speaking"], 1,
                   "Пассив настоящего → is spoken."),
            choice("The film was directed ___ a famous director.", ["by", "from", "with"], 0, "Кем → by."),
            choice("I ___ in Russia.", ["born", "was born", "am born"], 1, "was born."),
            text("Поставь в пассив: They make cars here. → Cars ___ here.",
                 ["are made"], "Cars <b>are made</b> here."),
        ],
    ),
]

LESSONS_BY_ID: dict[str, Lesson] = {lesson.id: lesson for lesson in LESSONS}

WEAK_SPOT_NAMES = {
    "verbs": "Формы глагола и времена",
    "conditionals": "Условные предложения",
    "articles": "Артикли, предлоги, мн. число",
    "other": "Прочее",
}
