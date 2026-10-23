/* =========================================================================
 * Sneh Saathi — interface text in all 13 languages.
 *
 * Answers come in the user's own language; this file covers the interface
 * around them (buttons, labels, messages). The interface follows the chosen
 * language, or on Auto the language the user last wrote in, else the phone's.
 *
 * English and Hindi are below, so the first screen never waits. The other 11
 * live in /i18n/<code>.json and load when first needed; a key missing there
 * falls back to English. Urdu switches the page to right-to-left.
 *
 * Static HTML marks text with data-i18n (textContent), data-i18n-ph
 * (placeholder), data-i18n-aria (aria-label) and data-i18n-title (title).
 * Plain, everyday wording on purpose: many readers are older.
 * ========================================================================= */

const STRINGS = {
  en: {
    skip: "Skip to message box",
    openMenu: "Open chats and settings",
    pageTitle: "Sneh Saathi · Help for persons with disabilities",
    brandTag: "Help for persons with disabilities · 13 Indian languages",
    install: "Install app",
    textSize: "Text size",
    textSizeAria: "Text size: {size}",
    textSizeLabel: "Text: {size}",
    sizeNormal: "normal", sizeLarge: "large", sizeXl: "extra large",
    contrast: "High contrast",
    speak: "Speak answers",
    newChat: "New chat",
    closeMenu: "Close chats and settings",
    recentChats: "Recent chats",
    settings: "Settings",
    answerLanguage: "Language",
    autoDetect: "Auto-detect (recommended)",
    langHelp: "The app and its answers use this language. Auto-detect follows the language you speak or write in.",
    sidebarAria: "Chats and settings",
    chatAria: "Conversation",
    composerAria: "Send a message",
    privacy: "Your chats are saved only in this browser, on this device.",
    greeting: "Namaste",
    homeSub: "Government help for persons with disabilities and their families.",
    homeLede: "Pensions, scholarships, the UDID card, aids and devices, schools and more. Type or speak in any Indian language.",
    topicsAria: "Popular topics",
    askByVoice: "Ask by voice",
    tapAndSpeak: "Tap and speak",
    listeningTap: "Listening… tap to stop",
    stopRecording: "Stop recording",
    examplesAria: "Example questions",
    getAppTitle: "Get the app on your phone",
    getAppApk: "Download Android app (APK)",
    getAppIOS: "On iPhone: tap the Share button at the bottom of Safari, then \"Add to Home Screen\".",
    getAppMenu: "Open your browser menu (⋮) and tap \"Install app\" or \"Add to Home screen\". It gets its own icon and opens full-screen.",
    getAppReady: "Install it to get an icon on your home screen. It opens full-screen, like any app.",
    homeNote: "Sneh Saathi is an independent student project, not a government website. Answers come from official government sources; confirm on the official portal before applying. Your chats stay in this browser.",
    stopDoc: "Stop using this document",
    attach: "Ask about a document (PDF or text)",
    placeholder: "Ask about any scheme…",
    placeholderShort: "Type or tap the mic",
    message: "Message",
    send: "Send message",
    matches: "Matches",
    matchesCount: "Matches: {n} schemes",
    yourMatches: "Your matches",
    closeMatches: "Close matches",
    profileTitle: "Your profile",
    profileEmpty: "Tell us your state, age, type of disability and family income. We'll check which schemes you qualify for.",
    profile_state: "State", profile_age: "Age", profile_disability: "Disability",
    profile_disability_percent: "Disability %", profile_income: "Family income", profile_occupation: "Occupation",
    schemesTitle: "Matched schemes",
    checkingSchemes: "Checking schemes…",
    schemesEmpty: "Matching schemes will appear here as we talk.",
    sourcesTitle: "Sources used",
    sources: "Sources",
    panelNote: "Eligibility is a guide based on what you've shared. Confirm on the official portal before applying.",
    autoChip: "Auto", autoChipAria: "Auto-detect language",
    moreChip: "More…", moreChipAria: "More languages",
    listen: "Listen", stop: "Stop", copy: "Copy", copied: "Copied",
    copyFailed: "Couldn't copy. Select the text and copy it instead.",
    seeMatches: "See {n} matching schemes", seeMatch: "See 1 matching scheme",
    followupsAria: "Suggested follow-up questions",
    deleteChat: "Delete chat: {title}",
    typing: "Sneh Saathi is typing",
    thinking: "Thinking…",
    eligible: "Eligible", checkDetails: "Check details", notEligible: "Not eligible",
    askAboutThis: "Ask about this", askAboutAria: "Ask about {name}",
    askAboutQ: "Tell me more about {name}: benefits, eligibility and how to apply.",
    opensOfficial: "(opens official site)",
    preparingAudio: "Preparing audio…",
    noVoice: "Voice output isn't available for this language yet.",
    audioFailed: "Couldn't prepare the audio. Try again.",
    micUnsupported: "Voice input isn't supported in this browser.",
    micDenied: "Microphone permission was denied. Allow it in your browser settings.",
    listening: "Listening… tap the mic again to stop.",
    transcribing: "Understanding what you said…",
    notHeard: "Couldn't hear that clearly. Try again.",
    transcribeFailed: "Couldn't understand the recording. Try again.",
    reading: "Reading “{name}”…",
    askAboutDoc: "Ask anything about “{name}”.",
    usingDoc: "Using “{name}” in this chat",
    unreadable: "Couldn't read that file. Try a PDF or text file.",
    uploadFailed: "Upload failed. Try again.",
    noAnswer: "Couldn't get an answer",
    tryAgain: "Try again",
    errorCode: "Error code: {code}",
    err_offline: "You seem to be offline. Check your internet connection, then try again.",
    err_network: "Couldn't reach Sneh Saathi. Check your internet connection, then try again.",
    err_server: "Sneh Saathi ran into a problem. Try again in a moment.",
    err_too_many_requests: "You've sent a lot of questions in a short time. Wait a few minutes, then try again.",
    err_rate_limit: "Sneh Saathi is getting too many questions right now. Wait a minute, then try again.",
    topics: [
      { icon: "cash", name: "Pension", hint: "Monthly financial support", q: "Which disability pension schemes can I get?" },
      { icon: "school", name: "Scholarship", hint: "School, college and abroad", q: "What scholarships are available for students with disabilities?" },
      { icon: "id", name: "UDID card", hint: "Apply, track, download", q: "How do I apply for a UDID card?" },
      { icon: "accessible", name: "Aids and devices", hint: "Wheelchairs, hearing aids", q: "How can I get free aids and appliances like a wheelchair or hearing aid?" },
      { icon: "stethoscope", name: "Health and therapy", hint: "Insurance, therapy, early help", q: "What health insurance and therapy schemes are there for persons with disabilities?" },
      { icon: "building", name: "Schools and centres", hint: "Near where you live", q: "Which schools and centres near me can help my child with a disability?" },
    ],
    examples: [
      "I'm 34, live in Delhi and have 60% locomotor disability. Which pension can I get?",
      "Scholarships for a visually impaired college student?",
      "Health insurance for a child with autism?",
      "What are my rights under the RPwD Act 2016?",
    ],
  },

  hi: {
    skip: "संदेश लिखने की जगह पर जाएँ",
    openMenu: "बातचीत और सेटिंग खोलें",
    pageTitle: "स्नेह साथी · दिव्यांगजनों के लिए मदद",
    brandTag: "दिव्यांगजनों के लिए मदद · 13 भारतीय भाषाएँ",
    install: "ऐप इंस्टॉल करें",
    textSize: "अक्षर का आकार",
    textSizeAria: "अक्षर का आकार: {size}",
    textSizeLabel: "अक्षर: {size}",
    sizeNormal: "सामान्य", sizeLarge: "बड़ा", sizeXl: "और बड़ा",
    contrast: "हाई कंट्रास्ट",
    speak: "जवाब बोलकर सुनाएँ",
    newChat: "नई बातचीत",
    closeMenu: "बंद करें",
    recentChats: "पिछली बातचीत",
    settings: "सेटिंग",
    answerLanguage: "भाषा",
    autoDetect: "अपने-आप पहचानें (सुझाया गया)",
    langHelp: "पूरा ऐप और उसके जवाब इसी भाषा में होंगे। “अपने-आप पहचानें” चुनने पर आप जिस भाषा में बोलें या लिखें, वही अपनाई जाती है।",
    sidebarAria: "बातचीत और सेटिंग",
    chatAria: "बातचीत",
    composerAria: "संदेश भेजें",
    privacy: "आपकी बातचीत सिर्फ़ इसी ब्राउज़र में, इसी डिवाइस पर सहेजी जाती है।",
    greeting: "नमस्ते",
    homeSub: "दिव्यांगजनों और उनके परिवारों के लिए सरकारी मदद।",
    homeLede: "पेंशन, छात्रवृत्ति, UDID कार्ड, उपकरण, स्कूल और बहुत कुछ। किसी भी भारतीय भाषा में लिखें या बोलें।",
    topicsAria: "मुख्य विषय",
    askByVoice: "बोलकर पूछें",
    tapAndSpeak: "बोलकर पूछें",
    listeningTap: "सुन रहे हैं… रोकने के लिए दबाएँ",
    stopRecording: "रिकॉर्डिंग रोकें",
    examplesAria: "उदाहरण सवाल",
    getAppTitle: "अपने फ़ोन पर ऐप पाएँ",
    getAppApk: "Android ऐप डाउनलोड करें (APK)",
    getAppIOS: "iPhone पर: Safari में नीचे Share बटन दबाएँ, फिर \"Add to Home Screen\" चुनें।",
    getAppMenu: "ब्राउज़र का मेन्यू (⋮) खोलें और \"Install app\" या \"Add to Home screen\" दबाएँ। फ़ोन पर इसका अपना आइकन बन जाएगा।",
    getAppReady: "इंस्टॉल करें, फ़ोन की होम स्क्रीन पर इसका आइकन बन जाएगा और यह ऐप की तरह खुलेगा।",
    homeNote: "स्नेह साथी एक स्वतंत्र छात्र परियोजना है, सरकारी वेबसाइट नहीं। जवाब सरकारी स्रोतों से लिए जाते हैं; आवेदन से पहले आधिकारिक पोर्टल पर पुष्टि करें। आपकी बातचीत इसी ब्राउज़र में रहती है।",
    stopDoc: "यह दस्तावेज़ हटाएँ",
    attach: "किसी दस्तावेज़ (PDF) के बारे में पूछें",
    placeholder: "किसी भी योजना के बारे में पूछें…",
    placeholderShort: "लिखें या माइक दबाएँ",
    message: "संदेश",
    send: "भेजें",
    matches: "योजनाएँ",
    matchesCount: "{n} योजनाएँ",
    yourMatches: "आपके लिए योजनाएँ",
    closeMatches: "बंद करें",
    profileTitle: "आपकी जानकारी",
    profileEmpty: "अपना राज्य, उम्र, दिव्यांगता का प्रकार और परिवार की आय बताइए। हम देखेंगे कि आप किन योजनाओं के पात्र हैं।",
    profile_state: "राज्य", profile_age: "उम्र", profile_disability: "दिव्यांगता",
    profile_disability_percent: "दिव्यांगता %", profile_income: "परिवार की आय", profile_occupation: "काम-धंधा",
    schemesTitle: "आपसे मिलती योजनाएँ",
    checkingSchemes: "योजनाएँ देखी जा रही हैं…",
    schemesEmpty: "बातचीत के साथ आपकी योजनाएँ यहाँ दिखेंगी।",
    sourcesTitle: "स्रोत",
    sources: "स्रोत",
    panelNote: "पात्रता आपकी दी गई जानकारी पर आधारित अनुमान है। आवेदन से पहले आधिकारिक पोर्टल पर पुष्टि करें।",
    autoChip: "अपने-आप", autoChipAria: "भाषा अपने-आप पहचानें",
    moreChip: "और…", moreChipAria: "और भाषाएँ",
    listen: "सुनें", stop: "रोकें", copy: "कॉपी", copied: "कॉपी हो गया",
    copyFailed: "कॉपी नहीं हो सका। टेक्स्ट चुनकर कॉपी करें।",
    seeMatches: "{n} मिलती योजनाएँ देखें", seeMatch: "1 मिलती योजना देखें",
    followupsAria: "आगे के सुझाए सवाल",
    deleteChat: "बातचीत हटाएँ: {title}",
    typing: "स्नेह साथी जवाब लिख रहा है",
    thinking: "सोच रहे हैं…",
    eligible: "पात्र", checkDetails: "जाँच करें", notEligible: "पात्र नहीं",
    askAboutThis: "इसके बारे में पूछें", askAboutAria: "{name} के बारे में पूछें",
    askAboutQ: "{name} के बारे में बताइए: लाभ, पात्रता और आवेदन कैसे करें।",
    opensOfficial: "(आधिकारिक साइट खुलेगी)",
    preparingAudio: "आवाज़ तैयार हो रही है…",
    noVoice: "इस भाषा में अभी आवाज़ उपलब्ध नहीं है।",
    audioFailed: "आवाज़ तैयार नहीं हो सकी। फिर कोशिश करें।",
    micUnsupported: "इस ब्राउज़र में बोलकर पूछना संभव नहीं है।",
    micDenied: "माइक की अनुमति नहीं मिली। ब्राउज़र की सेटिंग में अनुमति दें।",
    listening: "सुन रहे हैं… रोकने के लिए माइक फिर दबाएँ।",
    transcribing: "आपकी बात समझी जा रही है…",
    notHeard: "आवाज़ साफ़ सुनाई नहीं दी। फिर कोशिश करें।",
    transcribeFailed: "रिकॉर्डिंग समझ नहीं आई। फिर कोशिश करें।",
    reading: "“{name}” पढ़ा जा रहा है…",
    askAboutDoc: "अब “{name}” के बारे में कुछ भी पूछें।",
    usingDoc: "इस बातचीत में “{name}” इस्तेमाल हो रहा है",
    unreadable: "यह फ़ाइल पढ़ी नहीं जा सकी। PDF या टेक्स्ट फ़ाइल आज़माएँ।",
    uploadFailed: "अपलोड नहीं हो सका। फिर कोशिश करें।",
    noAnswer: "जवाब नहीं मिल सका",
    tryAgain: "फिर कोशिश करें",
    errorCode: "त्रुटि कोड: {code}",
    err_offline: "इंटरनेट कनेक्शन नहीं है। कनेक्शन देखकर फिर कोशिश करें।",
    err_network: "स्नेह साथी से संपर्क नहीं हो सका। इंटरनेट देखकर फिर कोशिश करें।",
    err_server: "स्नेह साथी में कुछ गड़बड़ हुई। थोड़ी देर बाद फिर कोशिश करें।",
    err_too_many_requests: "आपने कम समय में बहुत सवाल भेजे हैं। कुछ मिनट रुककर फिर कोशिश करें।",
    err_rate_limit: "अभी बहुत लोग सवाल पूछ रहे हैं। एक मिनट रुककर फिर कोशिश करें।",
    topics: [
      { icon: "cash", name: "पेंशन", hint: "हर महीने आर्थिक मदद", q: "मुझे कौन सी दिव्यांग पेंशन योजनाएँ मिल सकती हैं?" },
      { icon: "school", name: "छात्रवृत्ति", hint: "स्कूल, कॉलेज और विदेश में पढ़ाई", q: "दिव्यांग छात्रों के लिए कौन सी छात्रवृत्तियाँ हैं?" },
      { icon: "id", name: "UDID कार्ड", hint: "आवेदन, स्थिति, डाउनलोड", q: "UDID कार्ड के लिए आवेदन कैसे करें?" },
      { icon: "accessible", name: "उपकरण", hint: "व्हीलचेयर, सुनने की मशीन", q: "व्हीलचेयर या सुनने की मशीन जैसे उपकरण मुफ़्त में कैसे मिलें?" },
      { icon: "stethoscope", name: "इलाज और थेरेपी", hint: "बीमा, थेरेपी, शुरुआती मदद", q: "दिव्यांगजनों के लिए स्वास्थ्य बीमा और थेरेपी की कौन सी योजनाएँ हैं?" },
      { icon: "building", name: "स्कूल और केंद्र", hint: "आपके आस-पास", q: "मेरे बच्चे की मदद के लिए आस-पास कौन से स्कूल और केंद्र हैं?" },
    ],
    examples: [
      "मेरी उम्र 34 साल है, मैं दिल्ली में रहता हूँ और 60% चलने-फिरने की दिव्यांगता है। मुझे कौन सी पेंशन मिलेगी?",
      "देख न पाने वाले कॉलेज छात्र के लिए छात्रवृत्ति?",
      "ऑटिज़्म वाले बच्चे के लिए स्वास्थ्य बीमा?",
      "दिव्यांगजन अधिकार अधिनियम 2016 में मेरे क्या अधिकार हैं?",
    ],
  },
};

// Every language the assistant answers in has an interface too.
const UI_LANGS = ["en", "hi", "ta", "te", "mr", "bn", "gu", "kn", "ml", "pa", "or", "as", "ur"];
const RTL_LANGS = new Set(["ur"]);

let UI_LANG = "en";

const uiLoads = {};  // code -> pending load, so quick taps share one download

/** Make sure the interface text for `code` is available; resolves false if it can't be loaded. */
function loadUiStrings(code) {
  if (STRINGS[code]) return Promise.resolve(true);
  if (!UI_LANGS.includes(code)) return Promise.resolve(false);
  // no-cache: always ask the server (a tiny 304 when unchanged), so a corrected
  // translation reaches people at once instead of after the browser's own guess.
  uiLoads[code] ??= fetch(`/i18n/${code}.json`, { cache: "no-cache" })
    .then((res) => (res.ok ? res.json() : null))
    .then((table) => { if (table) STRINGS[code] = table; return !!table; })
    .catch(() => false)  // offline and never loaded before: the caller falls back to English
    .finally(() => { delete uiLoads[code]; });
  return uiLoads[code];
}

/** Interface text for `key`, with {placeholders} filled from `vars`. */
function t(key, vars = {}) {
  const table = STRINGS[UI_LANG] || STRINGS.en;
  const text = key in table ? table[key] : (STRINGS.en[key] ?? key);
  return typeof text === "string" ? text.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "") : text;
}

/** Translate every marked element on the page (static HTML and generated). */
function translatePage(root = document) {
  document.documentElement.lang = UI_LANG;
  document.documentElement.dir = RTL_LANGS.has(UI_LANG) ? "rtl" : "ltr";
  document.title = t("pageTitle");
  root.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  root.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  root.querySelectorAll("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
  root.querySelectorAll("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); });
}
