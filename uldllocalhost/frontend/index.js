const __author__ = "kubik.augustyn@post.cz"

// **************
// Do the foldable elements
const foldables = new Map(new Array(document.querySelector(".foldable")).map(elem => [elem, false]))
new Array(document.querySelector(".foldButton")).forEach(button => {
    button.addEventListener("click", ev => {
        const button = ev.target
        if (!button.parentElement) return;
        let parent = button.parentElement
        if (!foldables.has(parent)) {
            if (!parent.parentElement) return;
            if (!foldables.has(parent.parentElement)) return
            parent = parent.parentElement
        }
        foldables.set(parent, !foldables.get(parent))
        const folded = foldables.get(parent)
        if (folded) parent.classList.remove("folded")
        else parent.classList.add("folded")
    })
})
// **************

const ge = (id) => document.getElementById(id)
let settings = undefined
let writtenData = ""
let downloadState = undefined
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

        this.captchaContainer = ge("captchaContainer")

        this.downloadStart = ge("downloadStart")
        this.downloadStop = ge("downloadStop")
        this.logging = ge("logging")

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
        if (data.type === "frontendMessage") onFrontendMessage(data.frontendMessage)
        else if (data.type === "download" && data.download === "stop") onDownloadStop()
        if (data?.source?.id) messageHandlers.get(data.source.id)?.(data)
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
let captchas = new Map()
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
const addCaptcha = (id, imageB64) => {
    window.scrollTo(0, 0)
    const div = document.createElement("div")
    div.innerHTML = `<img src="data:image/png;base64,${imageB64}" alt="Captcha prompt"><br>`
    var input = document.createElement("input")
    input.placeholder = "Kód z obrázku"
    input.type = "text"
    div.appendChild(input)
    input.select()
    var button = document.createElement("button")
    button.innerHTML = "OK"
    button.addEventListener("click", submitCaptchaFactory(id))
    div.appendChild(button)
    console.log("CAPTCHA PROMPT")
    div.dataset.id = id
    captchas.set(id, div)
    settingsElements.captchaContainer.appendChild(div)
}
const submitCaptchaFactory = id => {
    return () => {
        var div = captchas.get(id)
        var input = div.getElementsByTagName("input")[0]
        if (!input || !input.value) return
        captchas.delete(id)
        settingsElements.captchaContainer.removeChild(div)
        sendMessage({"type": "promptResponse", "promptResponse": input.value, "id": id})
    }
}

const colorText = text => {
    var colored = ""
    var coloredSpan
    var i = 0
    while (i < text.length) {
        var char = text.charAt(i)
        if (char === "\x1B") {
            if (coloredSpan) {
                coloredSpan.innerHTML = coloredSpan.innerText
                colored += coloredSpan.outerHTML
            }
            i += 2 // \x1B[
            var background = text.charAt(i).toUpperCase()
            i++
            var foreground
            if ("0123456789ABCDEF".includes(text.charAt(i))) {
                foreground = text.charAt(i).toUpperCase()
                i++
            } else if (text.charAt(i) !== "m") i -= 2
            coloredSpan = document.createElement("span")
            coloredSpan.dataset.background = background
            coloredSpan.dataset.foreground = foreground
            coloredSpan.classList.add("color")
        } else {
            if (coloredSpan) coloredSpan.innerText += char
            else colored += char
        }
        i++
    }
    if (coloredSpan) {
        coloredSpan.innerHTML = coloredSpan.innerText
        colored += coloredSpan.outerHTML
    }
    return colored
}

const onFrontendMessage = (message) => {
    console.log("Frontend message:", message)
    if (message.type === "print") settingsElements.logging.innerHTML += colorText(message.print) + "<br>"
    else if (message.type === "write") {
        if (message.write.endsWith("\r")) {
            message.write = message.write.slice(0, message.write.length - 2)
            writtenData += message.write
            onFrontendMessage({type: "flush"})
        } else writtenData += message.write
    } else if (message.type === "flush") {
        settingsElements.logging.innerHTML += colorText(writtenData) + "<br>"
        writtenData = ""
    } else if (message.type === "prompt") {
        if (message.prompt) {
            // Normal prompt
            sendMessage({"type": "promptResponse", "promptResponse": prompt(message.prompt), "id": message.id})
        } else {
            // Captcha prompt
            addCaptcha(message.id, message.promptCaptcha)
        }
    }
    window.scrollTo(0, document.body.getBoundingClientRect().height)
}

const downloadChange = data => {
    console.log("Download changed:", data)
    sendMessage({
        "type": "download",
        "download": "state"
    }, downloadStateChange)
}
const downloadStateChange = data => {
    downloadState = data.state
    console.log("Download state changed:", downloadState)
    switch (downloadState) {
        case "waiting":
            settingsElements.downloadStop.disabled = true
            settingsElements.downloadStart.disabled = false
            break
        case "running":
            settingsElements.downloadStop.disabled = false
            settingsElements.downloadStart.disabled = true
            break
        case "stopped":
            settingsElements.downloadStop.disabled = true
            settingsElements.downloadStart.disabled = true
            break
        case "done":
            settingsElements.downloadStop.disabled = true
            settingsElements.downloadStart.disabled = true
            break
        default:
            console.log("Not implemented state:", downloadState)
            break
    }
    // Reset captchaContainer
    if (downloadState !== "running") settingsElements.captchaContainer.innerHTML = ""
}
const onDownloadStop = () => {
    console.log("Download stopped!")
}

settingsElements.urlElemAdd.onclick = ev => {
    ev.preventDefault()
    settingsElements.addUrlElem()
}
settingsElements.settingsForm.onsubmit = ev => {
    ev.preventDefault()

    settings.urls = settingsElements.readUrls()

    settings.main.parts = parseInt(settingsElements.parts.value)
    settings.main.output = settingsElements.output.value
    settings.main.temp = settingsElements.temp.value
    settings.main.overwrite = settingsElements.overwrite.checked

    settings.log.partsProgress = settingsElements.partsProgress.checked
    settings.log.log = settingsElements.logFile.value

    settings.captcha.autoCaptcha = settingsElements.autoCaptcha.checked
    settings.captcha.manualCaptcha = settingsElements.manualCaptcha.checked
    settings.captcha.connTimeout = parseInt(settingsElements.connTimeout.value)

    settingsElements.loading("Saving settings...")
    sendMessage({"type": "save", "save": "settings", "settings": settings}, response => {
        // console.log("Saved settings:", response)
        settingsElements.stopLoading()
    })
}
settingsElements.downloadStart.onclick = () => {
    sendMessage({
        "type": "download",
        "download": "start"
    }, downloadChange)
}
settingsElements.downloadStop.onclick = () => {
    sendMessage({
        "type": "download",
        "download": "stop"
    }, downloadChange)
}

const onInit = () => {
    settingsElements.loading("Loading constants...")
    sendMessage({
        "type": "download",
        "download": "state"
    }, downloadStateChange)
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

