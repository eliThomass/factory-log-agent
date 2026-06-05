import React, { useState } from 'react';
import axios from 'axios';
import { Send, Bot, User, AlertTriangle, Activity, Package, Settings } from 'lucide-react';

interface PayloadData {
  underperforming_lines_count?: number | null;
  target_line_id?: string | null;
  low_stock_items?: string[] | null;
  bottleneck_station?: string | null;
}

interface Message {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  status?: string;
  payload?: PayloadData | null;
}

export default function App() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'init',
      sender: 'agent',
      text: "Factory Automation Network Online. Ask me about system throughput, low-stock inventory targets, or active station bottlenecks."
    }
  ]);
  const [loading, setLoading] = useState(false);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      sender: 'user',
      text: input
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await axios.post('http://127.0.0.1:8000/agent/chat', {
        text: userMessage.text,
        session_id: "react_session_demo"
      });

      const { status, message, data_payload } = response.data;

      setMessages((prev) => [...prev, {
        id: crypto.randomUUID(),
        sender: 'agent',
        text: message,
        status: status,
        payload: data_payload
      }]);
    } catch (error: any) {
      setMessages((prev) => [...prev, {
        id: crypto.randomUUID(),
        sender: 'agent',
        text: `API Connection Failed: ${error.message}`,
        status: 'ERROR'
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-icon">
          <Activity size={24} />
        </div>
        <div className="header-title">
          <h1>Factory Logs Dashboard</h1>
          <p>Multi-Agent Control Matrix (Sequential Flow Mode)</p>
        </div>
      </header>

      {/* Message Logs */}
      <div className="message-log">
        {messages.map((msg) => (
          <div key={msg.id} className={`message-row ${msg.sender === 'user' ? 'user-row' : 'agent-row'}`}>
            {msg.sender === 'agent' && (
              <div className="avatar">
                <Bot size={18} />
              </div>
            )}
            
            <div className="bubble">
              <p>{msg.text}</p>

              {/* Data Cards */}
              {msg.payload && Object.values(msg.payload).some(v => v !== null) && (
                <div className="telemetry-grid">
                  {msg.payload.underperforming_lines_count !== undefined && (
                    <div className="telemetry-card">
                      <AlertTriangle size={14} className="text-amber" />
                      <span>Struggling Lines: <strong className="text-amber">{msg.payload.underperforming_lines_count ?? 0}</strong></span>
                    </div>
                  )}
                  {msg.payload.target_line_id && (
                    <div className="telemetry-card">
                      <Activity size={14} className="text-blue" />
                      <span>Target Focus: <strong className="text-blue">{msg.payload.target_line_id}</strong></span>
                    </div>
                  )}
                  {msg.payload.bottleneck_station && (
                    <div className="telemetry-card">
                      <Settings size={14} className="text-purple" />
                      <span>Bottleneck Station: <strong className="text-purple">{msg.payload.bottleneck_station}</strong></span>
                    </div>
                  )}
                  {msg.payload.low_stock_items && msg.payload.low_stock_items.length > 0 && (
                    <div className="telemetry-card full-width">
                      <Package size={14} className="text-rose" />
                      <span>Depleted SKUs: <strong className="text-rose">{msg.payload.low_stock_items.join(', ')}</strong></span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {msg.sender === 'user' && (
              <div className="avatar">
                <User size={18} />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="loading-indicator">
            <span className="pulse">Agents running pipeline diagnostics...</span>
          </div>
        )}
      </div>

      {/* Input Footer Form */}
      <form onSubmit={sendMessage} className="action-form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Issue execution commands (e.g., 'Check line statuses')"
          className="action-input"
          disabled={loading}
        />
        <button type="submit" className="submit-btn" disabled={loading || !input.trim()}>
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}