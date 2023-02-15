const __author__ = "kubik.augustyn@post.cz"

const ge = (id) => document.getElementById(id)
let settings = undefined
let constants = {}
const getConst = (text) => {
    if (typeof text !== "string") return text
    if (text.search("const ") !== 0) return text
    return constants[text.slice(6)]
}
const settingsElements = new class {
    constructor() {
        this.loadingOverlay = ge("loadingOverlay")
        this.loadingMessage = ge("loadingMessage")

        this.settingsForm = ge("settingsForm")
        this.urls = ge("urls")
        this.urlElems = []
        this.urlElemAdd = ge("urlAdd")

        this.parts = ge("parts")
        this.output = ge("output")
        this.temp = ge("temp")
        this.overwrite = ge("overwrite")

        this.log = ge("log")
        this.partsProgress = ge("partsProgress")
        this.logFile = ge("logFile")

        this.captcha = ge("captcha")
        this.autoCaptcha = ge("autoCaptcha")
        this.manualCaptcha = ge("manualCaptcha")
        this.connTimeout = ge("connTimeout")

        Object.getOwnPropertyNames(Object.getPrototypeOf(this)).filter(method => (method !== 'constructor')).forEach((method) => {
            this[method] = this[method].bind(this);
        });
    }

    loading(message) {
        this.loadingMessage.innerHTML = message
        this.loadingOverlay.style.display = "block"
    }

    stopLoading() {
        this.loadingOverlay.style.display = "none"
    }

    addUrlElem(url) {
        const lastElem = this.urlElems[this.urlElems.length - 1]
        if (lastElem && !lastElem?.value) return // So we don't create blank inputs
        const inp = document.createElement("input")
        inp.type = "text"
        inp.size = 100
        inp.placeholder = "Zadejte URL"
        url && (inp.value = url)
        this.urlElems.push(inp)
        this.urls.removeChild(this.urlElemAdd)
        this.urls.appendChild(inp)
        this.urls.appendChild(document.createElement("br"))
        this.urls.appendChild(this.urlElemAdd)
    }

    readUrls() {
        return this.urlElems.filter(el => el.value).map(el => el.value)
    }
}
settingsElements.loading("Connecting to backend...")

const api = new WebSocket(`ws://${document.location.host}/api`)
api.onclose = () => {
    onMessage("info", "Connection closed")
    document.location.reload()
}
api.onmessage = (ev) => {
    let data = ev.data
    if (data.search("json") === 0) {
        data = JSON.parse(data.slice(4))
        if (data?.request?.id) messageHandlers.get(data.request.id)?.(data)
    }
    // console.log(data)
    onMessage(false, data)
}
api.onopen = () => {
    onMessage("info", "Established connection")
    settingsElements.stopLoading()
    onInit()
}

let messageHandlers = new Map()
const generateId = () => Math.random().toString(36).slice(2)
const sendMessage = (value, onload) => {
    if (!value) return
    if (value instanceof Object) {
        onload && messageHandlers.set(value.id = generateId(), onload)
        value = "json".concat(JSON.stringify(value))
    }
    api.send(value)
    onMessage(true, value)
}

const onMessage = (fromUser, text) => {
    // const p = document.createElement("p")
    const prefix = fromUser === "info" ? "Info: " : (fromUser ? ">>> " : "<<< ")
    // p.innerHTML = prefix.concat(text)
    // messages.appendChild(p)
    console.log(prefix, text)
}

settingsElements.urlElemAdd.onclick = ev => {
    ev.preventDefault()
    settingsElements.addUrlElem()
}
settingsElements.settingsForm.onsubmit = ev => {
    ev.preventDefault()

    settings.urls = settingsElements.readUrls()

    settings.main.parts = settingsElements.parts.value
    settings.main.output = settingsElements.output.value
    settings.main.temp = settingsElements.temp.value
    settings.main.overwrite = settingsElements.overwrite.checked

    settings.log.partsProgress = settingsElements.partsProgress.checked
    settings.log.log = settingsElements.logFile.value

    settings.captcha.autoCaptcha = settingsElements.autoCaptcha.checked
    settings.captcha.manualCaptcha = settingsElements.manualCaptcha.checked
    settings.captcha.connTimeout = settingsElements.connTimeout.value

    sendMessage({"type": "save", "save": "settings", "settings": settings}, response => {
        console.log("Saved settings:", response)
    })
}

const onInit = () => {
    settingsElements.loading("Loading constants...")
    sendMessage({"type": "request", "request": "constants"}, response => {
        constants = response.constants
        settingsElements.loading("Loading settings...")
        sendMessage({"type": "request", "request": "settings"}, response => {
            settings = response.settings
            console.log("Loaded settings:", settings)
            settings.urls.forEach(settingsElements.addUrlElem)

            settingsElements.parts.value = getConst(settings.main.parts)
            settingsElements.output.value = getConst(settings.main.output)
            settingsElements.temp.value = getConst(settings.main.temp)
            settingsElements.overwrite.checked = getConst(settings.main.overwrite)

            settingsElements.partsProgress.checked = getConst(settings.log.partsProgress)
            settingsElements.logFile.value = getConst(settings.log.log)

            settingsElements.autoCaptcha.checked = getConst(settings.captcha.autoCaptcha)
            settingsElements.manualCaptcha.checked = getConst(settings.captcha.manualCaptcha)
            settingsElements.connTimeout.value = getConst(settings.captcha.connTimeout)

            settingsElements.stopLoading()
        })
    })
}

