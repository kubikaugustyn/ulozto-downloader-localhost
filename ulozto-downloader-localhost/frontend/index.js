const __author__ = "kubik.augustyn@post.cz"

const message = document.getElementById("message")
const send = document.getElementById("send")
const messages = document.getElementById("messages")

const api = new WebSocket("/api")

send.addEventListener("click", () => {
    if (message.value) {
        api.send(message.value)
        onMessage(true, message.value)
    }
})

api.onmessage = (ev) => {
    console.log(ev.data)
    onMessage(false, ev.data.message)
}

const onMessage = (fromUser, text) => {
    const p = document.createElement("p")
    p.innerHTML = (fromUser ? ">>> " : "<<< ").concat(text)
    messages.appendChild(p)
}
