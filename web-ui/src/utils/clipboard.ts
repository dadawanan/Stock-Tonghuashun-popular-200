/**
 * 复制文本到剪贴板：优先 Async Clipboard API，失败时用 execCommand 兼容 Safari / Firefox 等。
 */
export async function copyToClipboard(text: string): Promise<void> {
  if (typeof window === "undefined") {
    throw new Error("clipboard unavailable");
  }

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // 非安全上下文、权限被拒或部分 Safari 场景下会失败，走降级
    }
  }

  if (!copyViaExecCommand(text)) {
    throw new Error("copy failed");
  }
}

function copyViaExecCommand(text: string): boolean {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.top = "0";
  ta.style.left = "0";
  ta.style.width = "1px";
  ta.style.height = "1px";
  ta.style.padding = "0";
  ta.style.border = "none";
  ta.style.outline = "none";
  ta.style.boxShadow = "none";
  ta.style.background = "transparent";
  ta.style.opacity = "0";
  ta.setAttribute("tabindex", "-1");
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  ta.setSelectionRange(0, text.length);
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } finally {
    document.body.removeChild(ta);
  }
  return ok;
}
