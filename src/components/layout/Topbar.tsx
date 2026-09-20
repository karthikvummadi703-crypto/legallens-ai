import React, { useState } from 'react';
import { 
  Menu, 
  Search, 
  Bell, 
  Upload, 
  ChevronDown, 
  FileText, 
  ShieldAlert, 
  CheckCircle2, 
  User,
  Sparkles,
  ExternalLink
} from 'lucide-react';
import { Logo } from '../brand/Logo';
import { Button } from '../ui/Button';
import { LegalDocument, UserProfile } from '../../types';

interface TopbarProps {
  user: UserProfile;
  activeDocument?: LegalDocument | null;
  allDocuments?: LegalDocument[];
  onSelectDocument?: (doc: LegalDocument) => void;
  onOpenUpload: () => void;
  onOpenMobileMenu: () => void;
  onNavigateToSettings?: () => void;
  onSelectView?: (view: any) => void;
  onSignOut?: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({
  user,
  activeDocument,
  allDocuments = [],
  onSelectDocument = (_doc: LegalDocument) => {},
  onOpenUpload,
  onOpenMobileMenu,
  onNavigateToSettings = () => {},
  onSelectView,
  onSignOut
}) => {
  const [showDocDropdown, setShowDocDropdown] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const notifications = [
    {
      id: 'notif-1',
      title: 'High attention clause detected',
      desc: 'Section 8 Early Termination penalty requires review.',
      time: '12m ago',
      urgent: true
    },
    {
      id: 'notif-2',
      title: 'Document analyzed successfully',
      desc: 'Master SaaS Agreement completed full clause mapping.',
      time: '1h ago',
      urgent: false
    },
    {
      id: 'notif-3',
      title: 'Upcoming obligation alert',
      desc: 'Written notice window approaching in 60 days.',
      time: '4h ago',
      urgent: false
    }
  ];

  return (
    <header
      id="legallens-topbar"
      className="sticky top-0 z-30 h-16 bg-[#080b11]/90 backdrop-blur-md border-b border-slate-800/80 px-4 sm:px-6 flex items-center justify-between gap-4 select-none"
    >
      {/* Left: Mobile hamburger & Document Switcher */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onOpenMobileMenu}
          className="lg:hidden p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          aria-label="Open menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="lg:hidden">
          <Logo size="xs" showText={false} />
        </div>

        {/* Active Document Selector Dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowDocDropdown(!showDocDropdown)}
            aria-haspopup="listbox"
            aria-expanded={showDocDropdown}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/90 hover:bg-slate-800/90 border border-slate-800 hover:border-slate-700 text-xs text-slate-200 transition-all cursor-pointer group"
          >
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
            <span className="text-slate-400 hidden sm:inline">Active:</span>
            <span className="font-semibold text-white truncate max-w-[160px] sm:max-w-[240px]">
              {activeDocument?.name || 'Select Document'}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 group-hover:text-white transition-transform" />
          </button>

          {showDocDropdown && (
            <>
              <div 
                className="fixed inset-0 z-40" 
                onClick={() => setShowDocDropdown(false)} 
              />
              <div className="absolute left-0 mt-2 w-72 sm:w-80 rounded-2xl bg-[#0d121d] border border-slate-700/80 shadow-2xl p-2 z-50 animate-in fade-in zoom-in-95">
                <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800">
                  Select Legal Document
                </div>
                <div className="max-h-60 overflow-y-auto py-1 space-y-1">
                  {allDocuments.map((doc) => (
                    <button
                      key={doc.id}
                      onClick={() => {
                        onSelectDocument(doc);
                        setShowDocDropdown(false);
                      }}
                      aria-current={activeDocument && doc.id === activeDocument.id ? 'true' : undefined}
                      className={`w-full flex items-center justify-between p-2 rounded-xl text-left text-xs transition-colors ${
                        activeDocument && doc.id === activeDocument.id 
                          ? 'bg-indigo-600/20 text-indigo-300 font-semibold border border-indigo-500/30' 
                          : 'text-slate-300 hover:bg-slate-800/60'
                      }`}
                    >
                      <div className="flex items-center gap-2 truncate">
                        <FileText className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                        <span className="truncate">{doc.name}</span>
                      </div>
                      <span className="text-[10px] font-mono font-bold text-slate-400 shrink-0 ml-2">
                        {doc.attentionScore}/100
                      </span>
                    </button>
                  ))}
                  {allDocuments.length === 0 && (
                    <div className="p-3 text-center text-xs text-slate-500">
                      No documents uploaded yet
                    </div>
                  )}
                </div>
                <div className="pt-2 border-t border-slate-800 px-1">
                  <button
                    onClick={() => {
                      setShowDocDropdown(false);
                      onOpenUpload();
                    }}
                    className="w-full flex items-center justify-center gap-2 py-1.5 text-xs text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10 rounded-lg transition-colors"
                  >
                    <Upload className="w-3 h-3" />
                    <span>Upload another document</span>
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Center Search Bar */}
      <div className="hidden md:flex items-center flex-1 max-w-md mx-4">
        <div className="relative w-full">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search clauses, terms, risks"
            placeholder="Search clauses, terms, risks (e.g. 'arbitration', 'clawback')..."
            className="w-full pl-9 pr-4 py-1.5 text-xs rounded-xl bg-slate-900/60 border border-slate-800 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/30 transition-all"
          />
        </div>
      </div>

      {/* Right Controls: Notifications, Upload, Profile */}
      <div className="flex items-center gap-2.5">
        {/* Quick Upload Button */}
        <Button
          variant="glow"
          size="sm"
          onClick={onOpenUpload}
          leftIcon={<Sparkles className="w-3.5 h-3.5" />}
          className="hidden sm:inline-flex text-xs"
        >
          Upload
        </Button>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors relative"
            aria-label="View notifications"
            aria-haspopup="dialog"
            aria-expanded={showNotifications}
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-indigo-500 ring-2 ring-[#080b11]" />
          </button>

          {showNotifications && (
            <>
              <div 
                className="fixed inset-0 z-40" 
                onClick={() => setShowNotifications(false)} 
              />
              <div className="absolute right-0 mt-2 w-80 rounded-2xl bg-[#0d121d] border border-slate-700/80 shadow-2xl p-3 z-50 animate-in fade-in zoom-in-95">
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800">
                  <span className="text-xs font-semibold text-white">Notifications & Alerts</span>
                  <span className="text-[10px] font-mono text-indigo-400 bg-indigo-500/15 px-1.5 py-0.5 rounded">
                    3 unread
                  </span>
                </div>
                <div className="space-y-2">
                  {notifications.map((n) => (
                    <div 
                      key={n.id}
                      className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800/80 hover:border-slate-700 transition-colors text-xs space-y-1 cursor-pointer"
                    >
                      <div className="flex items-center justify-between">
                        <span className={`font-semibold ${n.urgent ? 'text-rose-300' : 'text-slate-200'}`}>
                          {n.title}
                        </span>
                        <span className="text-[10px] text-slate-500">{n.time}</span>
                      </div>
                      <p className="text-slate-400 text-[11px] leading-relaxed">
                        {n.desc}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* User Profile Pill */}
<div
          onClick={onNavigateToSettings}
          role="button"
          tabIndex={0}
          aria-label="Open account settings"
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onNavigateToSettings();
            }
          }}
          className="flex items-center gap-2.5 pl-2 py-1 pr-3 rounded-xl bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800/80 cursor-pointer transition-all"
          title="Account Settings"
        >
          <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-indigo-600 to-violet-600 text-white flex items-center justify-center font-bold text-xs shadow-sm">
            {user?.name ? user.name.charAt(0).toUpperCase() : 'U'}
          </div>
          <div className="hidden xl:block text-left">
            <div className="text-xs font-semibold text-white tracking-tight leading-none">
              {user?.name ? user.name.split(' ')[0] : 'Counsel'}
            </div>
            <div className="text-[10px] text-slate-400 leading-none mt-0.5">
              {user?.role || 'General Counsel'}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
