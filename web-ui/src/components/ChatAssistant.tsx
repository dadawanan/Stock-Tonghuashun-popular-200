import { useState, useRef, useEffect, useCallback } from 'react';
import { Input } from 'antd';
import { v4 as uuidv4 } from 'uuid';
import {
  MessageOutlined,
  CloseOutlined,
  MinusOutlined,
  SendOutlined,
  ThunderboltOutlined,
  StockOutlined,
  FundOutlined,
  FileTextOutlined,
  RobotOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { chatApi } from '../utils';
import type { ChatMessage, IntentAction, ChatChunk } from '../utils';
import styles from './ChatAssistant.less';

/** 快捷操作配置 */
const QUICK_ACTIONS = [
  { icon: <StockOutlined />, label: '查看今日热门股票', query: '查看今日热门股票' },
  { icon: <FundOutlined />, label: '查看模拟账户', query: '查看我的模拟账户' },
  { icon: <FileTextOutlined />, label: '查看最新资讯', query: '查看最新资讯' },
  { icon: <ThunderboltOutlined />, label: '查看热门排行', query: '查看热门排行' },
];

export default function ChatAssistant() {
  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messageListRef = useRef<HTMLDivElement>(null);
  // #1: 同步锁，避免 stale closure 竞态
  const sendingRef = useRef(false);
  // #4: 标记面板是否关闭，避免 stale response 写入
  const closedRef = useRef(false);
  // #10: 用于取消未完成的请求
  const abortRef = useRef<AbortController | null>(null);

  /** 自动滚动到底部 */
  useEffect(() => {
    const el = messageListRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, loading]);

  /** 首次打开时添加欢迎消息 */
  useEffect(() => {
    if (open && messages.length === 0) {
      setMessages([
        {
          id: uuidv4(),
          role: 'assistant',
          content: 'Hi，我是智能助手～\n欢迎随时提问',
          timestamp: Date.now(),
          isWelcome: true,
        },
      ]);
    }
  }, [open, messages.length]);

  // #10: 组件卸载时取消未完成的请求
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const handleSend = useCallback(
    async (text?: string) => {
      const content = (text ?? input).trim();
      if (!content || sendingRef.current) return;

      sendingRef.current = true;
      setLoading(true);

      const userMsg: ChatMessage = {
        id: uuidv4(),
        role: 'user',
        content,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setInput('');

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        // Build history from current messages
        const history = [...messages, userMsg].map((m) => ({
          role: m.role,
          content: m.content,
        }));

        const response = await chatApi.sendMessage(content, history);

        if (closedRef.current) return;

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        const assistantId = uuidv4();
        let accumulated = '';
        let startedStreaming = false;

        // Add placeholder message for streaming
        setMessages((prev) => [
          ...prev,
          {
            id: assistantId,
            role: 'assistant',
            content: '',
            timestamp: Date.now(),
          },
        ]);

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const text = decoder.decode(value, { stream: true });
          const lines = text.split('\n');

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const dataStr = line.slice(6).trim();
            if (!dataStr) continue;

            try {
              const chunk: ChatChunk = JSON.parse(dataStr);

              if (chunk.type === 'token') {
                if (!startedStreaming) {
                  startedStreaming = true;
                  setLoading(false);
                }
                accumulated += chunk.content;
                const finalContent = accumulated;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, content: finalContent } : m,
                  ),
                );
              } else if (chunk.type === 'done') {
                break;
              } else if (chunk.type === 'error') {
                accumulated = chunk.content || '抱歉，AI 服务出错了。';
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, content: accumulated } : m,
                  ),
                );
              }
            } catch {
              // Skip non-JSON lines
            }
          }
        }
      } catch (err: any) {
        if (err?.name === 'AbortError') return;
        if (closedRef.current) return;
        setMessages((prev) => [
          ...prev,
          {
            id: uuidv4(),
            role: 'assistant',
            content: '抱歉，助手暂时无法响应。请检查 AI 服务是否已启动。',
            timestamp: Date.now(),
          },
        ]);
      } finally {
        sendingRef.current = false;
        setLoading(false);
      }
    },
    [input, messages],
  );

  const handleAction = useCallback((action: IntentAction) => {
    switch (action.type) {
      case 'navigate':
        if (action.payload?.path) {
          window.location.href = action.payload.path;
        }
        break;
      case 'query':
        // Trigger a new query with the action payload
        if (action.payload?.query) {
          handleSend(action.payload.query);
        }
        break;
      case 'analyze':
        if (action.payload?.stock_code) {
          window.location.href = `/?stock=${action.payload.stock_code}`;
        }
        break;
      default:
        break;
    }
  }, [handleSend]);

  /** 键盘事件 */
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  /** 关闭面板 */
  const handleClose = useCallback(() => {
    closedRef.current = true;
    abortRef.current?.abort();
    setOpen(false);
    setMinimized(false);
    setMessages([]);
    // 重置 closed 标记，下次打开时生效
    requestAnimationFrame(() => {
      closedRef.current = false;
    });
  }, []);

  /** 打开面板 */
  const handleOpen = useCallback(() => {
    closedRef.current = false;
    setOpen(true);
  }, []);

  return (
    <>
      {/* 悬浮球 */}
      {!open && (
        <button
          className={styles.floatingBtn}
          onClick={handleOpen}
          title="智能助手"
        >
          <MessageOutlined className={styles.icon} />
        </button>
      )}

      {/* 聊天面板 */}
      {open && (
        <div className={styles.panel} style={minimized ? { height: 56 } : undefined}>
          {/* 头部 */}
          <div className={styles.header}>
            <div>
              <div className={styles.title}>智能助手</div>
              {!minimized && (
                <div className={styles.subtitle}>有什么问题，都可以问我</div>
              )}
            </div>
            <div className={styles.actions}>
              <button onClick={() => setMinimized(!minimized)} title="最小化">
                <MinusOutlined />
              </button>
              <button onClick={handleClose} title="关闭">
                <CloseOutlined />
              </button>
            </div>
          </div>

          {/* 消息区域 */}
          {!minimized && (
            <>
              <div className={styles.messageList} ref={messageListRef}>
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`${styles.messageItem} ${styles[msg.role]}`}
                  >
                    <div className={styles.avatar}>
                      {msg.role === 'assistant' ? (
                        <RobotOutlined />
                      ) : (
                        <UserOutlined />
                      )}
                    </div>
                    <div className={styles.bubble}>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>

                      {/* 快捷操作（仅欢迎消息显示） */}
                      {msg.isWelcome && !msg.actions && (
                        <div className={styles.quickActions}>
                          {QUICK_ACTIONS.map((qa) => (
                            <button
                              key={qa.query}
                              className={styles.quickActionBtn}
                              onClick={() => handleSend(qa.query)}
                              // #8: loading 时禁用快捷操作
                              disabled={loading}
                            >
                              <span className={styles.icon}>{qa.icon}</span>
                              {qa.label}
                            </button>
                          ))}
                        </div>
                      )}

                      {/* 意图动作标签 */}
                      {msg.actions?.map((action, i) => (
                        <div
                          key={i}
                          className={styles.actionTag}
                          onClick={() => handleAction(action)}
                          style={{ cursor: 'pointer' }}
                        >
                          <ThunderboltOutlined />
                          {action.type}: {JSON.stringify(action.payload)}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}

                {/* 加载动画 */}
                {loading && (
                  <div className={`${styles.messageItem} ${styles.assistant}`}>
                    <div className={styles.avatar}>
                      <RobotOutlined />
                    </div>
                    <div className={styles.bubble}>
                      <div className={styles.loadingDots}>
                        <span />
                        <span />
                        <span />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* 输入区域 */}
              <div className={styles.inputArea}>
                <Input.TextArea
                  className={styles.input}
                  placeholder="输入你的问题..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  autoSize={{ minRows: 1, maxRows: 4 }}
                  disabled={loading}
                />
                <button
                  className={styles.sendBtn}
                  onClick={() => handleSend()}
                  disabled={!input.trim() || loading}
                  title="发送"
                >
                  <SendOutlined />
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
