#include <bits/stdc++.h>
#define int long long
#define par pair<int,int>
#define f first
#define s second
#define ld long double
#define ull unsigned long long 
#define st short int
#define int128 __int128_t
#define all(v) v.begin(),v.end()
#define rall(v) v.rbegin(),v.rend()
#define sz(v) (int)v.size()
#define vi vector <int>
#define vvi vector <vi>
#define vp vector <par>
#define vvp vector <vp>
#define INF 1e18
// #define INF 1e9 
#define EPS 1e-9

// #pragma GCC optimize("Ofast","unroll-loops","omit-frame-pointer","inline")
// #pragma GCC option ("arch=native","tune=native","no-zero-upper")
// #pragma GCC target ("avx2")

using namespace std; 

struct custom_hash{ 
    static uint64_t splitmix64(uint64_t x){
        x+=0x9e3779b97f4a7c15,x=(x^(x>>30))*0xbf58476d1ce4e5b9,x=(x^(x>>27))*0x94d049bb133111eb;
        return x^(x>>31);
    }
    size_t operator()(uint64_t x) const{
        static const uint64_t FIXED_RANDOM=chrono::steady_clock::now().time_since_epoch().count();
        return splitmix64(x+FIXED_RANDOM);
    }
};

const int mod=1e9+7;
const ld pi=acos(-1);
int arr[1000006],brr[1000006];
vi vec;
map <int,int> mapa;
// unordered_map <int,int,custom_hash> mapa;

int32_t main()
{
    ios_base::sync_with_stdio(0); cin.tie(0); cout.tie(0);
    int t; cin>>t;
    while(t--){
        
    }
     

    return 0;
}
//g++ -o main main.cpp
//./main 