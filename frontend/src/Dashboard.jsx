import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { newKey } from './api';

export default function Dashboard() {
  const [accounts, setAccounts] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [destination, setDestination] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [loadError, setLoadError] = useState('');
  // One key per transfer *intent*: double-clicks and network retries reuse it,
  // so the backend moves the money only once. A new key is made after success
  // or when the user edits the form.
  const keyRef = useRef(newKey());
  const [amount, setAmount] = useState('');
  const [message, setMessage] = useState({ text: '', type: '' });
  const navigate = useNavigate();

  const fetchData = async () => {
    try {
      const accRes = await api.get('/accounts');
      setAccounts(accRes.data);
      const txRes = await api.get('/transactions');
      setTransactions(txRes.data);
    } catch (err) {
      if (err.response?.status === 401) navigate('/login');
      else setLoadError('Could not load your account. Please refresh and try again.');
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleTransfer = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setMessage({ text: 'Processing transfer...', type: 'loading' });
    try {
      const res = await api.post('/transfers', {
        source_account_id: accounts[0].id,
        destination_account_number: destination.trim(),
        amount: parseFloat(amount),
        idempotency_key: keyRef.current
      });
      setMessage({ text: `Transfer Success! Ref: ${res.data.reference}`, type: 'success' });
      setAmount(''); setDestination('');
      keyRef.current = newKey();
      fetchData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setMessage({ text: typeof detail === 'string' ? detail : 'Transfer failed', type: 'error' });
    } finally {
      setSubmitting(false);
    }
    setTimeout(() => setMessage({ text: '', type: '' }), 5000);
  };

  if (accounts.length === 0) return <div className="min-h-screen flex items-center justify-center">{loadError || 'Loading...'}</div>;

  return (
    <div className="min-h-screen bg-gray-50 pb-12">
      {/* Top Navbar */}
      <nav className="bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">B</div>
          <span className="font-bold text-xl text-gray-900">Nexus</span>
        </div>
        <button onClick={() => { localStorage.removeItem('token'); navigate('/login'); }} className="text-gray-500 hover:text-gray-900 font-medium text-sm transition-colors">
          Log out
        </button>
      </nav>

      <div className="max-w-6xl mx-auto px-4 mt-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Account Card & Transfer Widget */}
        <div className="space-y-6 lg:col-span-1">
          {/* Virtual Card */}
          <div className="bg-gradient-to-br from-gray-900 to-blue-900 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
            <div className="absolute top-0 right-0 -mr-8 -mt-8 w-32 h-32 rounded-full bg-white opacity-10"></div>
            <p className="text-blue-200 text-sm font-medium mb-1">Available Balance</p>
            <h2 className="text-4xl font-bold mb-6">₹{accounts[0].balance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</h2>
            <div className="flex justify-between items-end">
              <div>
                <p className="text-xs text-blue-200 uppercase tracking-wider mb-1">Account Number</p>
                <p className="font-mono text-sm tracking-widest">{accounts[0].account_number}</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-blue-200 mb-1">Status</p>
                <p className="text-sm font-medium text-green-400">● Active</p>
              </div>
            </div>
          </div>

          {/* Transfer Form */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <h3 className="font-bold text-gray-900 mb-4">Send Money</h3>
            
            {message.text && (
              <div className={`p-3 text-sm rounded-lg mb-4 border ${message.type === 'success' ? 'bg-green-50 text-green-700 border-green-100' : message.type === 'error' ? 'bg-red-50 text-red-700 border-red-100' : 'bg-blue-50 text-blue-700 border-blue-100'}`}>
                {message.text}
              </div>
            )}

            <form onSubmit={handleTransfer} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 uppercase mb-1">Recipient Account Number</label>
                <input 
                  type="text" required placeholder="e.g. 456" value={destination} onChange={(e) => { setDestination(e.target.value); keyRef.current = newKey(); }} 
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 text-sm font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 uppercase mb-1">Amount (INR)</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">₹</div>
                  <input 
                    type="number" required step="0.01" placeholder="0.00" value={amount} onChange={(e) => { setAmount(e.target.value); keyRef.current = newKey(); }} 
                    className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 text-lg"
                  />
                </div>
              </div>
              <button type="submit" disabled={submitting} className="w-full bg-gray-900 hover:bg-black text-white font-medium py-3 rounded-lg shadow transition-colors disabled:opacity-50">
                {submitting ? 'Processing...' : 'Confirm Transfer'}
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Transaction Ledger */}
        <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-5 border-b border-gray-100 flex justify-between items-center bg-gray-50">
            <h3 className="font-bold text-gray-900">Transaction History</h3>
            <span className="text-xs text-gray-500 font-mono">Account: {accounts[0].account_number}</span>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-white border-b border-gray-100 text-xs uppercase text-gray-400 font-semibold tracking-wider">
                  <th className="px-6 py-4">Transaction Details</th>
                  <th className="px-6 py-4">Date</th>
                  <th className="px-6 py-4 text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {transactions.length === 0 ? (
                  <tr><td colSpan="3" className="px-6 py-8 text-center text-gray-500">No recent activity</td></tr>
                ) : (
                  transactions.map((tx) => {
                    const isSender = tx.source_account_id === accounts[0].id;
                    return (
                      <tr key={tx.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${isSender ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600'}`}>
                              {isSender ? '↑' : '↓'}
                            </div>
                            <div>
                              <p className="text-sm font-semibold text-gray-900">{isSender ? 'Funds Sent' : 'Funds Received'}</p>
                              <p className="text-xs text-gray-500 font-mono">{tx.reference_number}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-600">
                          {new Date(tx.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <p className={`font-bold ${isSender ? 'text-gray-900' : 'text-green-600'}`}>
                            {isSender ? '-' : '+'}₹{tx.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </p>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}