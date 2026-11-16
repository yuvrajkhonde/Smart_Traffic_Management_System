import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://hblpqicvqprvqryawvlo.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_GdKdsQbk5Abkz7Tr_xmi-w_NL9SxUjH';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);