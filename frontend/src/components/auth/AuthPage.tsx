import React, { useState } from 'react';
import { LoginPage } from './LoginPage';
import { RegisterPage } from './RegisterPage';

export const AuthPage: React.FC = () => {
  const [view, setView] = useState<'login' | 'register'>('login');
  if (view === 'register') {
    return <RegisterPage onNavigateToLogin={() => setView('login')} />;
  }
  return <LoginPage onNavigateToRegister={() => setView('register')} />;
};
