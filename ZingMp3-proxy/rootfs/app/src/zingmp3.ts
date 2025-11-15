import axios from "axios"
import crypto from "crypto"

class ZingMp3Api {
  public VERSION: string
  public URL: string
  public SECRET_KEY: string
  public API_KEY: string
  public CTIME: string

  constructor(VERSION: string, URL: string, SECRET_KEY: string, API_KEY: string, CTIME: string) {
    this.VERSION = VERSION
    this.URL = URL
    this.SECRET_KEY = SECRET_KEY
    this.API_KEY = API_KEY
    this.CTIME = CTIME
  }

  private getHash256(str: string) {
    return crypto.createHash("sha256")
                 .update(str)
                 .digest("hex")
  }

  private getHmac512(str: string, key: string) {
    let hmac = crypto.createHmac("sha512", key)
    return hmac.update(Buffer.from(str, "utf8"))
               .digest("hex")
  }

  private hashParamNoId(path: string) {
    return this.getHmac512(
      path + this.getHash256(`ctime=${this.CTIME}version=${this.VERSION}`),
      this.SECRET_KEY
    )
  }

  private hashParam(path: string, id: string) {
    return this.getHmac512(
      path + this.getHash256(`ctime=${this.CTIME}id=${id}version=${this.VERSION}`),
      this.SECRET_KEY
    )
  }

  private hashParamHome(path: string) {
    return this.getHmac512(
      path + this.getHash256(`count=30ctime=${this.CTIME}page=1version=${this.VERSION}`),
      this.SECRET_KEY
    )
  }

  private hashCategoryMV (path: string, id: string, type: string) {
    return this.getHmac512(
      path + this.getHash256(`ctime=${this.CTIME}id=${id}type=${type}version=${this.VERSION}`),
      this.SECRET_KEY
    );
  }

  private hashListMV (path: string, id: string, type: string, page: string, count: string) {
    return this.getHmac512(
      path +
        this.getHash256(
          `count=${count}ctime=${this.CTIME}id=${id}page=${page}type=${type}version=${this.VERSION}`
        ),
      this.SECRET_KEY
    );
  }

  private getCookie(): Promise<any> {
    return new Promise<any>((resolve, rejects) => {
        axios.get(`${this.URL}`)
          .then((res) => {
            if(res.headers["set-cookie"]) {
              res.headers["set-cookie"].map((element, index) => {
                if(index == 1) {
                  resolve(element)
                }
              })
            }
          })
          .catch((err) => {
            rejects(err)
          })
      }
    )
  }

  private requestZingMp3(path: string, qs: object): Promise<any> {
    return new Promise<any>((resolve, rejects) => {
      const client = axios.create({
        baseURL: `${this.URL}`,
      });

      client.interceptors.response.use((res: any) => res.data);

      this.getCookie()
        .then((cookie) => {
          client.get(path, {
            headers: {
              Cookie: `${cookie}`,
            },
            params: {
              ...qs,
              ctime: this.CTIME,
              version: this.VERSION,
              apiKey: this.API_KEY,
            }
          })
            .then((res) => {
              resolve(res)
            })
            .catch((err) => {
              rejects(err)
            })
        })
        .catch((err) => {
          console.log(err)
        })
    })
  }

  public getSong(songId: string): Promise<any> {
    return new Promise<any>((resolve, rejects) => {
      this.requestZingMp3("/api/v2/song/get/streaming", {
        id: songId,
        sig: this.hashParam("/api/v2/song/get/streaming", songId)
      })
        .then((res) => {
          resolve(res)
        })
        .catch((err) => {
          rejects(err)
        })
    })
  }

  public getInfoSong(songId: string): Promise<any> {
    return new Promise<any>((resolve, rejects) => {
      this.requestZingMp3("/api/v2/song/get/info", {
        id: songId,
        sig: this.hashParam("/api/v2/song/get/info", songId)
      })
        .then((res) => {
          resolve(res)
        })
        .catch((err) => {
          rejects(err)
        })
    })
  }

  public search(name: string): Promise<any> {
    return new Promise<any>((resolve, rejects) => {
      this.requestZingMp3("/api/v2/search/multi", {
        q: name,
        sig: this.hashParamNoId("/api/v2/search/multi")
      })
        .then((res) => {
          resolve(res)
        })
        .catch((err) => {
          rejects(err)
        })
    })
  }

  public getDetailPlaylist(playlistId: string): Promise<any> {
    return new Promise<any>((resolve, rejects) => {
      this.requestZingMp3("/api/v2/page/get/playlist", {
        id: playlistId,
        sig: this.hashParam("/api/v2/page/get/playlist", playlistId)
      })
        .then((res) => {
          resolve(res)
        })
        .catch((err) => {
          rejects(err)
        })
    })
  }
}

export const ZingMp3 = new ZingMp3Api(
  "1.6.34",
  "https://zingmp3.vn",
  "2aa2d1c561e809b267f3638c4a307aab",
  "88265e23d4284f25963e6eedac8fbfa3",
  String(Math.floor(Date.now() / 1000))
)
